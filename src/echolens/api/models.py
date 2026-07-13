"""Typed response models for the EchoLens frontend API."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def _to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class ApiModel(BaseModel):
    """Base model that serializes snake_case Python fields as camelCase JSON."""

    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)


class HealthResponse(ApiModel):
    status: str = "ok"


class TagCount(ApiModel):
    tag: str
    count: int


class CreatorSummary(ApiModel):
    platform: str
    sec_uid: str
    name: str | None = None
    video_count: int = 0
    completed_count: int = 0
    top_tags: list[str] = Field(default_factory=list)
    updated_at: datetime | None = None


class VideoSummary(ApiModel):
    id: int
    platform: str
    video_id: str
    creator_sec_uid: str
    creator_name: str | None = None
    description: str | None = None
    summary: str | None = None
    tags: list[str] = Field(default_factory=list)
    key_points: list[str] = Field(default_factory=list)
    published_at: datetime | None = None
    status: str
    updated_at: datetime | None = None


class DashboardResponse(ApiModel):
    creator_count: int
    video_count: int
    completed_count: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    top_tags: list[TagCount] = Field(default_factory=list)
    recent_videos: list[VideoSummary] = Field(default_factory=list)


class CreatorListResponse(ApiModel):
    items: list[CreatorSummary]
    total: int


class CreatorDetailResponse(ApiModel):
    creator: CreatorSummary
    top_tags: list[TagCount] = Field(default_factory=list)
    videos: list[VideoSummary] = Field(default_factory=list)


class TranscriptSegment(ApiModel):
    start: float
    end: float
    text: str


class VideoDetail(VideoSummary):
    transcript: str | None = None
    segments: list[TranscriptSegment] = Field(default_factory=list)
    language: str | None = None
    audio_size: int | None = None
    audio_url: str | None = None
    transcription_model: str | None = None
    analysis_model: str | None = None


class SearchResponse(ApiModel):
    items: list[VideoSummary]
    total: int


def json_string_list(value: Any) -> list[str]:
    """Normalize a MySQL JSON list into clean strings."""

    if value is None:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return []
    if not isinstance(value, list):
        return []
    return [normalized for item in value if (normalized := str(item).strip())]


def transcript_segments(value: Any) -> list[TranscriptSegment]:
    """Normalize timestamped transcript segments stored as MySQL JSON."""

    if value is None:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return []
    if not isinstance(value, list):
        return []

    result: list[TranscriptSegment] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        try:
            result.append(
                TranscriptSegment(
                    start=float(item.get("start", 0.0)),
                    end=float(item.get("end", 0.0)),
                    text=str(item.get("text", "")).strip(),
                )
            )
        except (TypeError, ValueError):
            continue
    return result


def published_datetime(value: Any) -> datetime | None:
    """Convert provider epoch seconds or milliseconds into UTC."""

    if value is None:
        return None
    try:
        timestamp = float(value)
    except (TypeError, ValueError):
        return None
    if timestamp > 100_000_000_000:
        timestamp /= 1000
    try:
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def tag_counts(rows: list[dict[str, Any]], limit: int = 12) -> list[TagCount]:
    """Aggregate tags from analysis rows in descending frequency order."""

    counter: Counter[str] = Counter()
    for row in rows:
        counter.update(json_string_list(row.get("tags_json")))
    return [TagCount(tag=tag, count=count) for tag, count in counter.most_common(limit)]


def video_summary_from_row(row: dict[str, Any]) -> VideoSummary:
    return VideoSummary(
        id=int(row["id"]),
        platform=str(row["platform"]),
        video_id=str(row["video_id"]),
        creator_sec_uid=str(row["creator_sec_uid"]),
        creator_name=row.get("creator_name"),
        description=row.get("description"),
        summary=row.get("summary"),
        tags=json_string_list(row.get("tags_json")),
        key_points=json_string_list(row.get("key_points_json")),
        published_at=published_datetime(row.get("source_create_time")),
        status=str(row["status"]),
        updated_at=row.get("updated_at"),
    )


def creator_summary_from_row(
    row: dict[str, Any],
    *,
    top_tags: list[str] | None = None,
) -> CreatorSummary:
    return CreatorSummary(
        platform=str(row["platform"]),
        sec_uid=str(row["sec_uid"]),
        name=row.get("creator_name"),
        video_count=int(row.get("video_count") or 0),
        completed_count=int(row.get("completed_count") or 0),
        top_tags=top_tags or [],
        updated_at=row.get("updated_at"),
    )
