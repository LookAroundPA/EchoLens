"""Deterministic creator-level knowledge aggregation from completed videos."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pydantic import Field

from echolens.api.evidence import key_point_evidence, normalize_text
from echolens.api.models import (
    ApiModel,
    CreatorSummary,
    TagCount,
    VideoSummary,
    json_string_list,
    transcript_segments,
    video_summary_from_row,
)


class CreatorPointSource(ApiModel):
    video_id: int
    title: str
    published_at: datetime | None = None
    start: float | None = None
    end: float | None = None
    segment_index: int | None = None
    excerpt: str | None = None


class CreatorInsight(ApiModel):
    text: str
    occurrence_count: int
    sources: list[CreatorPointSource] = Field(default_factory=list)


class RepresentativeVideo(VideoSummary):
    reason: str


class CreatorProfile(ApiModel):
    overview: str
    analyzed_video_count: int = 0
    main_themes: list[TagCount] = Field(default_factory=list)
    insights: list[CreatorInsight] = Field(default_factory=list)
    representative_videos: list[RepresentativeVideo] = Field(default_factory=list)
    recent_videos: list[VideoSummary] = Field(default_factory=list)


class CreatorProfileResponse(ApiModel):
    creator: CreatorSummary
    top_tags: list[TagCount] = Field(default_factory=list)
    videos: list[VideoSummary] = Field(default_factory=list)
    profile: CreatorProfile


@dataclass
class _InsightCluster:
    variants: Counter[str] = field(default_factory=Counter)
    normalized_variants: list[str] = field(default_factory=list)
    sources_by_video: dict[int, CreatorPointSource] = field(default_factory=dict)

    @property
    def text(self) -> str:
        return max(
            self.variants,
            key=lambda item: (self.variants[item], len(normalize_text(item))),
        )

    @property
    def occurrence_count(self) -> int:
        return len(self.sources_by_video)


def build_creator_profile(
    creator_name: str | None,
    rows: list[dict[str, Any]],
) -> CreatorProfile:
    """Build a compact creator profile from already analyzed local videos."""

    if not rows:
        return CreatorProfile(
            overview="尚无已完成的分析内容。完成视频处理后，这里会自动汇总主题、观点和代表内容。",
        )

    theme_counter: Counter[str] = Counter()
    clusters: list[_InsightCluster] = []
    video_entries: list[tuple[RepresentativeVideo, float, datetime | None]] = []

    for row in rows:
        summary = video_summary_from_row(row)
        tags = json_string_list(row.get("tags_json"))
        points = json_string_list(row.get("key_points_json"))
        segments = transcript_segments(row.get("segments_json"))
        evidence_by_point = {
            item.key_point_index: item
            for item in key_point_evidence(points, segments)
        }
        theme_counter.update(tags)

        for point_index, point in enumerate(points):
            normalized = normalize_text(point)
            if len(normalized) < 4:
                continue
            source_evidence = evidence_by_point.get(point_index)
            source = CreatorPointSource(
                video_id=summary.id,
                title=summary.description or summary.summary or f"视频 {summary.video_id}",
                published_at=summary.published_at,
                start=source_evidence.start if source_evidence else None,
                end=source_evidence.end if source_evidence else None,
                segment_index=source_evidence.segment_index if source_evidence else None,
                excerpt=source_evidence.text if source_evidence else point,
            )
            cluster = _matching_cluster(clusters, normalized)
            if cluster is None:
                cluster = _InsightCluster()
                clusters.append(cluster)
            cluster.variants[point] += 1
            cluster.normalized_variants.append(normalized)
            cluster.sources_by_video.setdefault(summary.id, source)

        completeness_score = (
            (5.0 if summary.summary else 0.0)
            + min(len(tags), 6) * 1.25
            + min(len(points), 8) * 1.6
            + len(evidence_by_point) * 1.1
        )
        reasons: list[str] = []
        if tags:
            reasons.append(f"覆盖 {'、'.join(tags[:3])}")
        if points:
            reasons.append(f"包含 {len(points)} 条关键观点")
        if evidence_by_point:
            reasons.append(f"{len(evidence_by_point)} 条可回溯来源")
        video_entries.append(
            (
                RepresentativeVideo(
                    **summary.model_dump(),
                    reason="；".join(reasons) or "内容信息较完整",
                ),
                completeness_score,
                summary.published_at,
            )
        )

    themes = [
        TagCount(tag=tag, count=count)
        for tag, count in theme_counter.most_common(12)
    ]
    insights = _finalize_insights(clusters)
    representative_videos = [
        item[0]
        for item in sorted(
            video_entries,
            key=lambda item: (
                item[1],
                item[2].timestamp() if item[2] is not None else 0.0,
                item[0].id,
            ),
            reverse=True,
        )[:6]
    ]
    recent_videos = [video_summary_from_row(row) for row in rows[:8]]

    return CreatorProfile(
        overview=_overview(
            creator_name=creator_name,
            completed_count=len(rows),
            themes=themes,
            insights=insights,
        ),
        analyzed_video_count=len(rows),
        main_themes=themes,
        insights=insights[:10],
        representative_videos=representative_videos,
        recent_videos=recent_videos,
    )


def _matching_cluster(
    clusters: list[_InsightCluster],
    normalized: str,
) -> _InsightCluster | None:
    best: tuple[float, _InsightCluster] | None = None
    for cluster in clusters:
        score = max(
            (_text_similarity(normalized, candidate) for candidate in cluster.normalized_variants),
            default=0.0,
        )
        if score >= 0.58 and (best is None or score > best[0]):
            best = (score, cluster)
    return best[1] if best else None


def _text_similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    if left in right or right in left:
        shorter = min(len(left), len(right))
        longer = max(len(left), len(right))
        return 0.72 + shorter / max(1, longer) * 0.28
    left_grams = _ngrams(left)
    right_grams = _ngrams(right)
    intersection = len(left_grams & right_grams)
    union = len(left_grams | right_grams)
    if intersection < 2 or union == 0:
        return 0.0
    jaccard = intersection / union
    coverage = intersection / max(1, min(len(left_grams), len(right_grams)))
    return jaccard * 0.55 + coverage * 0.45


def _ngrams(value: str, size: int = 2) -> set[str]:
    if len(value) <= size:
        return {value}
    return {value[index : index + size] for index in range(len(value) - size + 1)}


def _finalize_insights(clusters: list[_InsightCluster]) -> list[CreatorInsight]:
    result: list[CreatorInsight] = []
    for cluster in clusters:
        sources = sorted(
            cluster.sources_by_video.values(),
            key=lambda item: (
                item.start is not None,
                item.published_at.timestamp() if item.published_at is not None else 0.0,
                item.video_id,
            ),
            reverse=True,
        )[:4]
        result.append(
            CreatorInsight(
                text=cluster.text,
                occurrence_count=cluster.occurrence_count,
                sources=sources,
            )
        )
    return sorted(
        result,
        key=lambda item: (
            item.occurrence_count,
            sum(source.start is not None for source in item.sources),
            len(normalize_text(item.text)),
        ),
        reverse=True,
    )


def _overview(
    *,
    creator_name: str | None,
    completed_count: int,
    themes: list[TagCount],
    insights: list[CreatorInsight],
) -> str:
    subject = creator_name or "该创作者"
    sentences = [f"{subject} 当前已沉淀 {completed_count} 条完成内容。"]
    if themes:
        sentences.append(f"主要主题集中在{'、'.join(item.tag for item in themes[:5])}。")
    if insights:
        sentences.append(
            "较有代表性的观点包括："
            + "；".join(item.text for item in insights[:3])
            + "。"
        )
    else:
        sentences.append("现有内容尚未提取出足够稳定的关键观点。")
    return "".join(sentences)
