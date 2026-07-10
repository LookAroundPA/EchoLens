"""Local source directory scanner."""

import json
import time
from collections.abc import Iterator
from pathlib import Path

from pydantic import ValidationError

from echolens.collector.local_models import LocalVideoItem, LocalVideoMetadata
from echolens.core.config import Settings, get_settings


class LocalSourceScanner:
    """Scan local Douyin video files and their sidecar metadata."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def scan(self) -> list[LocalVideoItem]:
        """Return stable local video items with valid sidecar metadata."""

        return list(self.iter_items())

    def iter_items(self) -> Iterator[LocalVideoItem]:
        """Yield local video items discovered from the source directory."""

        source_dir = self.settings.douyin_source_dir
        if not source_dir.exists():
            return

        for video_path in source_dir.rglob("*.mp4"):
            if not video_path.is_file():
                continue
            if not self._is_stable(video_path):
                continue
            item = self._build_item(video_path)
            if item is not None:
                yield item

    def _is_stable(self, video_path: Path) -> bool:
        """Return whether a file looks stable enough to process."""

        stat = video_path.stat()
        age_seconds = time.time() - stat.st_mtime
        return age_seconds >= self.settings.scan_stability_seconds

    def _build_item(self, video_path: Path) -> LocalVideoItem | None:
        """Build a normalized item from a video and its sidecar metadata."""

        metadata_path = video_path.with_suffix(video_path.suffix + ".json")
        if not metadata_path.exists():
            return None

        try:
            raw_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata = LocalVideoMetadata.model_validate(raw_metadata)
        except (OSError, json.JSONDecodeError, ValidationError):
            return None

        stat = video_path.stat()
        return LocalVideoItem(
            platform=metadata.platform,
            author_id=metadata.author_id,
            video_id=metadata.video_id,
            source_path=video_path,
            metadata_path=metadata_path,
            file_name=video_path.name,
            file_size=stat.st_size,
            file_mtime=stat.st_mtime,
            desc=metadata.desc,
            create_time=metadata.create_time,
            downloaded_at=metadata.downloaded_at,
            raw_metadata=raw_metadata,
        )
