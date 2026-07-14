"""Deterministic evidence matching for search hits and key points."""

from __future__ import annotations

import re
from typing import Any, Iterable

from echolens.api.models import KeyPointEvidence, SearchMatch, TranscriptSegment


_NORMALIZE_PATTERN = re.compile(r"[^0-9a-z\u3400-\u9fff]+", re.IGNORECASE)


def normalize_text(value: str) -> str:
    """Normalize multilingual text for small local similarity comparisons."""

    return _NORMALIZE_PATTERN.sub("", value.casefold())


def excerpt(text: str, query: str, radius: int = 72) -> str:
    """Return a compact excerpt around an exact case-insensitive match."""

    clean = text.strip()
    if not clean:
        return ""
    position = clean.casefold().find(query.casefold())
    if position < 0:
        return clean[: radius * 2] + ("…" if len(clean) > radius * 2 else "")
    start = max(0, position - radius)
    end = min(len(clean), position + len(query) + radius)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(clean) else ""
    return f"{prefix}{clean[start:end].strip()}{suffix}"


def search_match(row: dict[str, Any], query: str) -> SearchMatch:
    """Find the most useful visible source for one SQL-matched video row."""

    segments = _segments(row.get("segments_json"))
    segment_match = _exact_segment_window(segments, query)
    if segment_match is not None:
        return segment_match

    fields = (
        ("description", row.get("description")),
        ("summary", row.get("summary")),
    )
    for match_type, value in fields:
        text = str(value or "")
        if query.casefold() in text.casefold():
            return SearchMatch(match_type=match_type, text=excerpt(text, query))

    for point in _string_list(row.get("key_points_json")):
        if query.casefold() in point.casefold():
            return SearchMatch(match_type="key_point", text=excerpt(point, query))

    for tag in _string_list(row.get("tags_json")):
        if query.casefold() in tag.casefold():
            return SearchMatch(match_type="tag", text=tag)

    transcript = str(row.get("transcript_text") or "")
    if query.casefold() in transcript.casefold():
        return SearchMatch(match_type="transcript", text=excerpt(transcript, query))

    return SearchMatch(
        match_type="content",
        text=str(row.get("summary") or row.get("description") or "匹配到该视频内容"),
    )


def key_point_evidence(
    key_points: Iterable[str],
    segments: list[TranscriptSegment],
) -> list[KeyPointEvidence]:
    """Link each key point to its best one-to-three-segment transcript window."""

    windows = list(_segment_windows(segments, max_size=3))
    results: list[KeyPointEvidence] = []
    for key_point_index, key_point in enumerate(key_points):
        normalized_point = normalize_text(key_point)
        if len(normalized_point) < 4:
            continue

        best: tuple[float, int, int, float, float, str] | None = None
        for segment_index, segment_count, start, end, text in windows:
            score = _similarity(normalized_point, normalize_text(text))
            if segment_count > 1:
                score -= 0.015 * (segment_count - 1)
            if best is None or score > best[0]:
                best = (score, segment_index, segment_count, start, end, text)

        if best is None or best[0] < 0.16:
            continue
        score, segment_index, segment_count, start, end, text = best
        results.append(
            KeyPointEvidence(
                key_point_index=key_point_index,
                segment_index=segment_index,
                segment_count=segment_count,
                start=start,
                end=end,
                text=text,
                score=round(max(0.0, min(1.0, score)), 3),
            )
        )
    return results


def _exact_segment_window(
    segments: list[TranscriptSegment],
    query: str,
) -> SearchMatch | None:
    normalized_query = normalize_text(query)
    if not normalized_query:
        return None
    for segment_index, segment_count, start, end, text in _segment_windows(
        segments,
        max_size=3,
    ):
        if normalized_query in normalize_text(text):
            return SearchMatch(
                match_type="transcript",
                text=excerpt(text, query),
                start=start,
                end=end,
                segment_index=segment_index,
                segment_count=segment_count,
            )
    return None


def _segment_windows(
    segments: list[TranscriptSegment],
    *,
    max_size: int,
):
    for start_index in range(len(segments)):
        for size in range(1, min(max_size, len(segments) - start_index) + 1):
            window = segments[start_index : start_index + size]
            parts = [item.text.strip() for item in window if item.text.strip()]
            text = _join_segment_text(parts)
            if not text:
                continue
            yield (
                start_index,
                size,
                float(window[0].start),
                float(window[-1].end),
                text,
            )


def _join_segment_text(parts: list[str]) -> str:
    result = ""
    for part in parts:
        if not result:
            result = part
            continue
        left = result[-1]
        right = part[0]
        separator = " " if (
            left.isascii()
            and right.isascii()
            and left.isalnum()
            and right.isalnum()
        ) else ""
        result += separator + part
    return result


def _similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    if left in right:
        return 1.0
    if right in left:
        return min(0.95, len(right) / max(1, len(left)) * 0.9)
    left_grams = _ngrams(left)
    right_grams = _ngrams(right)
    overlap = len(left_grams & right_grams)
    if overlap < 2:
        return 0.0
    coverage = overlap / max(1, len(left_grams))
    precision = overlap / max(1, len(right_grams))
    return coverage * 0.78 + min(1.0, precision * 2.0) * 0.22


def _ngrams(value: str, size: int = 2) -> set[str]:
    if len(value) <= size:
        return {value}
    return {value[index : index + size] for index in range(len(value) - size + 1)}


def _segments(value: Any) -> list[TranscriptSegment]:
    from echolens.api.models import transcript_segments

    return transcript_segments(value)


def _string_list(value: Any) -> list[str]:
    from echolens.api.models import json_string_list

    return json_string_list(value)
