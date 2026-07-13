"""Models for local source files produced by the external collector."""

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LocalAuthorMetadata(BaseModel):
    """Creator identity embedded in the provider sidecar metadata."""

    model_config = ConfigDict(extra="allow")

    sec_uid: str = Field(min_length=1)
    uid: str | None = None
    nickname: str | None = None

    @field_validator("sec_uid")
    @classmethod
    def validate_sec_uid(cls, value: str) -> str:
        """Reject an empty or whitespace-only stable creator identifier."""

        normalized = value.strip()
        if not normalized:
            raise ValueError("author.sec_uid must not be empty")
        return normalized


class LocalVideoMetadata(BaseModel):
    """Metadata stored in the provider sidecar ``.mp4.json`` file."""

    model_config = ConfigDict(extra="allow")

    video_id: str = Field(min_length=1)
    author_id: str = Field(min_length=1)
    author: LocalAuthorMetadata
    platform: str = "douyin"
    type: Literal["video"] = "video"
    desc: str | None = None
    create_time: int | None = None
    statistics: dict[str, Any] | None = None
    with_watermark: bool | None = None
    file_name: str = Field(min_length=1)
    file_path: str | None = None
    file_size: int | None = None
    file_mtime: float | None = None
    downloaded_at: str | None = None

    @field_validator("video_id", "author_id", "platform", "file_name")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        """Reject required text fields that only contain whitespace."""

        normalized = value.strip()
        if not normalized:
            raise ValueError("required metadata text field must not be empty")
        return normalized


class LocalVideoItem(BaseModel):
    """Normalized local video item consumed by EchoLens."""

    platform: str = "douyin"
    creator_sec_uid: str
    provider_author_id: str
    author_uid: str | None = None
    creator_name: str | None = None
    video_id: str
    source_path: Path
    metadata_path: Path
    file_name: str
    file_size: int
    file_mtime: float
    desc: str | None = None
    create_time: int | None = None
    downloaded_at: str | None = None
    statistics: dict[str, Any] = Field(default_factory=dict)
    raw_metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def dedupe_key(self) -> tuple[str, str, str]:
        """Return the stable video dedupe key."""

        return self.platform, self.creator_sec_uid, self.video_id
