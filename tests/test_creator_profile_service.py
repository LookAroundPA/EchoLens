from __future__ import annotations

from datetime import datetime, timezone
import json
import unittest

from echolens.api.service import FrontendService


class CreatorProfileRepository:
    def get_creator(self, sec_uid):
        if sec_uid != "creator-1":
            return None
        return {
            "platform": "douyin",
            "sec_uid": sec_uid,
            "creator_name": "创作者",
            "video_count": 2,
            "completed_count": 2,
            "updated_at": datetime(2026, 7, 14, tzinfo=timezone.utc),
        }

    def completed_tag_rows(self, creator_sec_uid=None):
        return [
            {"creator_sec_uid": "creator-1", "tags_json": json.dumps(["AI", "效率"])},
            {"creator_sec_uid": "creator-1", "tags_json": json.dumps(["AI"])},
        ]

    def creator_videos(self, sec_uid, limit=100):
        return [self._summary_row(2), self._summary_row(1)]

    def get_video(self, video_db_id):
        row = self._summary_row(video_db_id)
        row.update(
            {
                "audio_path": f"/data/{video_db_id}.wav",
                "audio_size": 1024,
                "transcript_text": "人工智能可以减少重复劳动",
                "segments_json": json.dumps(
                    [
                        {
                            "start": 5.0,
                            "end": 10.0,
                            "text": "人工智能可以减少重复劳动",
                        }
                    ],
                    ensure_ascii=False,
                ),
                "language": "zh",
                "transcription_model": "large-v3",
                "analysis_model": "deepseek",
            }
        )
        return row

    @staticmethod
    def _summary_row(video_db_id):
        point = "人工智能可以减少重复劳动" if video_db_id == 2 else "人工智能减少重复劳动"
        return {
            "id": video_db_id,
            "platform": "douyin",
            "video_id": f"source-{video_db_id}",
            "creator_sec_uid": "creator-1",
            "creator_name": "创作者",
            "description": f"视频 {video_db_id}",
            "source_create_time": 1_720_000_000 - video_db_id,
            "status": "done",
            "updated_at": datetime(2026, 7, 14, tzinfo=timezone.utc),
            "summary": "视频摘要",
            "tags_json": json.dumps(["AI", "效率"], ensure_ascii=False),
            "key_points_json": json.dumps([point], ensure_ascii=False),
        }


class CreatorProfileServiceTests(unittest.TestCase):
    def test_creator_detail_contains_profile_and_playable_sources(self) -> None:
        service = FrontendService(CreatorProfileRepository())

        result = service.creator_detail("creator-1", limit=100)
        assert result is not None
        payload = result.model_dump(by_alias=True)

        self.assertEqual(payload["creator"]["secUid"], "creator-1")
        self.assertEqual(payload["profile"]["analyzedVideoCount"], 2)
        self.assertEqual(payload["profile"]["mainThemes"][0]["tag"], "AI")
        self.assertEqual(payload["profile"]["insights"][0]["occurrenceCount"], 2)
        self.assertEqual(payload["profile"]["insights"][0]["sources"][0]["start"], 5.0)
        self.assertEqual(len(payload["profile"]["representativeVideos"]), 2)
        self.assertEqual(len(payload["videos"]), 2)

    def test_missing_creator_returns_none(self) -> None:
        service = FrontendService(CreatorProfileRepository())

        self.assertIsNone(service.creator_detail("missing", limit=100))


if __name__ == "__main__":
    unittest.main()
