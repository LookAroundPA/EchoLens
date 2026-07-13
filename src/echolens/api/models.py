"""Typed response and request models for the EchoLens frontend API."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from enum import Enum
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


class VideoListResponse(ApiModel):
    items: list[VideoSummary]
    total: int


class TagListResponse(ApiModel):
    items: list[TagCount]


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


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class ProcessingJob(ApiModel):
    id: int
    video_id: int | None = None
    job_type: str
    status: JobStatus
    retry_count: int = 0
    payload: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class JobListResponse(ApiModel):
    items: list[ProcessingJob]
    total: int


class ScanActionRequest(ApiModel):
    enqueue: bool = True


class PipelineActionRequest(ApiModel):
    scan: bool = True
    max_tasks: int | None = Field(default=None, ge=1, le=10000)


class VideoProcessStage(str, Enum):
    current = "current"
    audio = "audio"
    transcription = "transcription"
    analysis = "analysis"


class VideoProcessRequest(ApiModel):
    stage: VideoProcessStage = VideoProcessStage.current
    continue_to_done: bool = True


def json_value(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return value


def json_string_list(value: Any) -> list[str]:
    """Normalize a MySQL JSON list into clean strings."""

    value = json_value(value, [])
    if not isinstance(value, list):
        return []
    return [normalized for item in value if (normalized := str(item).strip())]


def transcript_segments(value: Any) -> list[TranscriptSegment]:
    """Normalize timestamped transcript segments stored as MySQL JSON."""

    value = json_value(value, [])
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


def processing_job_from_row(row: dict[str, Any]) -> ProcessingJob:
    payload = json_value(row.get("payload_json"), {})
    result = json_value(row.get("result_json"), None)
    return ProcessingJob(
        id=int(row["id"]),
        video_id=(int(row["video_id"]) if row.get("video_id") is not None else None),
        job_type=str(row["job_type"]),
        status=JobStatus(str(row["status"])),
        retry_count=int(row.get("retry_count") or 0),
        payload=payload if isinstance(payload, dict) else {},
        result=result if isinstance(result, dict) else None,
        error_message=row.get("error_message"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        started_at=row.get("started_at"),
        finished_at=row.get("finished_at"),
    )
