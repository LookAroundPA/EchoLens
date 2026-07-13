"""Models used by the read-only knowledge query layer."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field


def _json_string_list(value: Any) -> list[str]:
    """Normalize a MySQL JSON value into a clean list of strings."""

    if value is None:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return []
    if not isinstance(value, list):
        return []

    result: list[str] = []
    for item in value:
        normalized = str(item).strip()
        if normalized:
            result.append(normalized)
    return result


class CreatorKnowledgeSummary(BaseModel):
    """One creator and the amount of completed knowledge available."""

    platform: str
    sec_uid: str
    creator_name: str | None = None
    video_count: int = 0
    done_count: int = 0

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "CreatorKnowledgeSummary":
        return cls(
            platform=str(row["platform"]),
            sec_uid=str(row["sec_uid"]),
            creator_name=row.get("creator_name"),
            video_count=int(row.get("video_count") or 0),
            done_count=int(row.get("done_count") or 0),
        )


class KnowledgeItem(BaseModel):
    """A completed video joined with transcript and analysis data."""

    db_id: int
    platform: str
    video_id: str
    creator_sec_uid: str
    creator_name: str | None = None
    description: str | None = None
    source_create_time: int | None = None
    status: str
    summary: str | None = None
    tags: list[str] = Field(default_factory=list)
    key_points: list[str] = Field(default_factory=list)
    analysis_model: str | None = None
    language: str | None = None
    transcript_text: str | None = None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "KnowledgeItem":
        return cls(
            db_id=int(row["db_id"]),
            platform=str(row["platform"]),
            video_id=str(row["video_id"]),
            creator_sec_uid=str(row["creator_sec_uid"]),
            creator_name=row.get("creator_name"),
            description=row.get("description"),
            source_create_time=(
                int(row["source_create_time"])
                if row.get("source_create_time") is not None
                else None
            ),
            status=str(row["status"]),
            summary=row.get("summary"),
            tags=_json_string_list(row.get("tags_json")),
            key_points=_json_string_list(row.get("key_points_json")),
            analysis_model=row.get("analysis_model"),
            language=row.get("language"),
            transcript_text=row.get("transcript_text"),
        )
