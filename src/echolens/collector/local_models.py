"""Models for local source files produced by the external collector."""

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


class LocalVideoMetadata(BaseModel):
    """Metadata stored in the sidecar .mp4.json file."""

    video_id: str
    author_id: str
    platform: str = "douyin"
    type: Literal["video"] = "video"
    desc: str | None = None
    create_time: int | None = None
    with_watermark: bool | None = None
    file_name: str
    file_path: str | None = None
    file_size: int | None = None
    file_mtime: float | None = None
    downloaded_at: str | None = None


class LocalVideoItem(BaseModel):
    """Normalized local video item consumed by EchoLens."""

    platform: str = "douyin"
    author_id: str
    video_id: str
    source_path: Path
    metadata_path: Path
    file_name: str
    file_size: int
    file_mtime: float
    desc: str | None = None
    create_time: int | None = None
    downloaded_at: str | None = None
    raw_metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def dedupe_key(self) -> tuple[str, str, str]:
        """Return the primary dedupe key."""

        return self.platform, self.author_id, self.video_id
