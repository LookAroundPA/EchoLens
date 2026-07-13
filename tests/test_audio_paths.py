"""Tests for local and Docker path handling in the audio worker."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from echolens.audio.ffmpeg import output_path_for, resolve_source_path
from echolens.core.config import Settings


class AudioPathTests(unittest.TestCase):
    def test_maps_legacy_windows_source_path_into_runtime_mount(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            runtime_root = Path(temporary_directory)
            video_path = runtime_root / "creator" / "video.mp4"
            video_path.parent.mkdir()
            video_path.touch()
            settings = Settings(
                douyin_source_dir=runtime_root,
                douyin_source_host_dir=r"D:\BaiduNetdiskDownload\dy src",
            )

            resolved = resolve_source_path(
                r"D:\BaiduNetdiskDownload\dy src\creator\video.mp4",
                settings,
            )

            self.assertEqual(resolved, video_path)

    def test_output_path_uses_stable_creator_identity(self) -> None:
        settings = Settings(audio_output_dir=Path("/data/audio"))
        output_path = output_path_for(
            {
                "platform": "douyin",
                "creator_sec_uid": "MS4w/a\\b",
                "video_id": "123",
            },
            settings,
        )

        self.assertEqual(output_path, Path("/data/audio/douyin/MS4w_a_b/123.wav"))

    def test_output_path_accepts_legacy_author_id_during_migration(self) -> None:
        settings = Settings(audio_output_dir=Path("/data/audio"))
        output_path = output_path_for(
            {"platform": "douyin", "author_id": "legacy", "video_id": "123"},
            settings,
        )

        self.assertEqual(output_path, Path("/data/audio/douyin/legacy/123.wav"))
