"""Tests for the external local source provider protocol."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from echolens.collector.local_scanner import LocalSourceScanner
from echolens.core.config import Settings


class LocalSourceProtocolTests(unittest.TestCase):
    def _write_source(self, root: Path, metadata: dict[str, object]) -> Path:
        creator_dir = root / "provider-author-directory"
        creator_dir.mkdir(parents=True)
        video_path = creator_dir / "douyin.wtf_douyin_7103469551442038030.mp4"
        video_path.write_bytes(b"video")
        metadata_path = video_path.with_suffix(".mp4.json")
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
        return video_path

    def _metadata(self) -> dict[str, object]:
        return {
            "video_id": "7103469551442038030",
            "author_id": "黄士铨看世界_1116730602555796",
            "author": {
                "uid": "1116730602555796",
                "nickname": "黄士铨看世界",
                "sec_uid": "MS4wLjABAAAARGJtMMMujtgxbnl18CQHeUiTdopr5C--P4I3t80KvumwcZw2di4vfeteEnBhYI-x",
                "unknown_provider_field": "preserved in raw metadata",
            },
            "platform": "douyin",
            "type": "video",
            "desc": "创业，是我人生的转折点。",
            "create_time": 1653905399,
            "statistics": {
                "comment_count": 1412,
                "digg_count": 20470,
                "play_count": 0,
            },
            "with_watermark": False,
            "file_name": "douyin.wtf_douyin_7103469551442038030.mp4",
            "file_path": "/app/download/provider-author-directory/video.mp4",
            "file_size": 19771412,
            "file_mtime": 1783839855.4939942,
            "downloaded_at": "2026-07-12T07:04:15.509194+00:00",
        }

    def test_uses_author_sec_uid_as_creator_and_video_dedupe_identity(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self._write_source(root, self._metadata())
            scanner = LocalSourceScanner(
                Settings(douyin_source_dir=root, scan_stability_seconds=0)
            )

            items = scanner.scan()

            self.assertEqual(len(items), 1)
            item = items[0]
            self.assertEqual(
                item.creator_sec_uid,
                "MS4wLjABAAAARGJtMMMujtgxbnl18CQHeUiTdopr5C--P4I3t80KvumwcZw2di4vfeteEnBhYI-x",
            )
            self.assertEqual(item.provider_author_id, "黄士铨看世界_1116730602555796")
            self.assertEqual(item.author_uid, "1116730602555796")
            self.assertEqual(item.creator_name, "黄士铨看世界")
            self.assertEqual(item.dedupe_key, ("douyin", item.creator_sec_uid, item.video_id))
            self.assertEqual(item.statistics["digg_count"], 20470)
            self.assertEqual(scanner.issues, [])

    def test_missing_sec_uid_is_skipped_and_recorded_as_protocol_error(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            metadata = self._metadata()
            del metadata["author"]["sec_uid"]  # type: ignore[index]
            self._write_source(root, metadata)
            scanner = LocalSourceScanner(
                Settings(douyin_source_dir=root, scan_stability_seconds=0)
            )

            items = scanner.scan()

            self.assertEqual(items, [])
            self.assertEqual(len(scanner.issues), 1)
            issue = scanner.issues[0]
            self.assertEqual(issue.code, "metadata_protocol_error")
            self.assertIn("author.sec_uid is required", issue.message)


if __name__ == "__main__":
    unittest.main()
