"""Local source directory scanner."""

import json
import logging
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from echolens.collector.local_models import LocalVideoItem, LocalVideoMetadata
from echolens.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScanIssue:
    """A structured reason why one local source file was skipped."""

    code: str
    message: str
    video_path: Path
    metadata_path: Path


class LocalSourceScanner:
    """Scan local Douyin video files and their sidecar metadata."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.issues: list[ScanIssue] = []

    def scan(self) -> list[LocalVideoItem]:
        """Return stable local video items with valid sidecar metadata."""

        self.issues.clear()
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

    def _record_issue(
        self,
        code: str,
        message: str,
        video_path: Path,
        metadata_path: Path,
    ) -> None:
        issue = ScanIssue(
            code=code,
            message=message,
            video_path=video_path,
            metadata_path=metadata_path,
        )
        self.issues.append(issue)
        logger.warning(
            "Local source item skipped: code=%s video=%s metadata=%s message=%s",
            code,
            video_path,
            metadata_path,
            message,
        )

    def _build_item(self, video_path: Path) -> LocalVideoItem | None:
        """Build a normalized item from a video and its sidecar metadata."""

        metadata_path = video_path.with_suffix(video_path.suffix + ".json")
        if not metadata_path.exists():
            self._record_issue(
                "metadata_missing",
                "sidecar metadata file is required",
                video_path,
                metadata_path,
            )
            return None

        try:
            raw_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except OSError as exc:
            self._record_issue(
                "metadata_read_failed",
                str(exc),
                video_path,
                metadata_path,
            )
            return None
        except json.JSONDecodeError as exc:
            self._record_issue(
                "metadata_parse_failed",
                str(exc),
                video_path,
                metadata_path,
            )
            return None

        try:
            metadata = LocalVideoMetadata.model_validate(raw_metadata)
        except ValidationError as exc:
            missing_sec_uid = any(
                tuple(error.get("loc", ())) == ("author", "sec_uid")
                for error in exc.errors()
            )
            message = (
                "author.sec_uid is required and must be a non-empty string"
                if missing_sec_uid
                else f"metadata does not match provider protocol: {exc}"
            )
            self._record_issue(
                "metadata_protocol_error",
                message,
                video_path,
                metadata_path,
            )
            return None

        stat = video_path.stat()
        return LocalVideoItem(
            platform=metadata.platform,
            creator_sec_uid=metadata.author.sec_uid,
            provider_author_id=metadata.author_id,
            author_uid=metadata.author.uid,
            creator_name=metadata.author.nickname,
            video_id=metadata.video_id,
            source_path=video_path,
            metadata_path=metadata_path,
            file_name=video_path.name,
            file_size=stat.st_size,
            file_mtime=stat.st_mtime,
            desc=metadata.desc,
            create_time=metadata.create_time,
            downloaded_at=metadata.downloaded_at,
            statistics=metadata.statistics or {},
            raw_metadata=raw_metadata,
        )
