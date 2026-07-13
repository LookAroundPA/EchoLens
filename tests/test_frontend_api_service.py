"""Tests for frontend-facing API response construction."""

from datetime import datetime
import json
import unittest

from echolens.api.service import FrontendService


class FakeFrontendRepository:
    def dashboard_counts(self):
        return {"creator_count": 2, "video_count": 4, "completed_count": 3}

    def status_counts(self):
        return [
            {"status": "audio_done", "item_count": 1},
            {"status": "done", "item_count": 3},
        ]

    def recent_videos(self, limit=10):
        return [self._video_row()]

    def completed_tag_rows(self, creator_sec_uid=None):
        rows = [
            {"creator_sec_uid": "creator-1", "tags_json": json.dumps(["AI", "商业"])},
            {"creator_sec_uid": "creator-1", "tags_json": json.dumps(["AI"])},
            {"creator_sec_uid": "creator-2", "tags_json": json.dumps(["教育"])},
        ]
        if creator_sec_uid:
            return [row for row in rows if row["creator_sec_uid"] == creator_sec_uid]
        return rows

    def list_creators(self, query=None, limit=100):
        return (
            [
                {
                    "platform": "douyin",
                    "sec_uid": "creator-1",
                    "creator_name": "创作者",
                    "video_count": 3,
                    "completed_count": 2,
                    "updated_at": datetime(2026, 7, 13, 12, 0, 0),
                }
            ],
            1,
        )

    def get_creator(self, sec_uid):
        if sec_uid != "creator-1":
            return None
        return self.list_creators()[0][0]

    def creator_videos(self, sec_uid, limit=100):
        return [self._video_row()]

    def search_videos(self, query, creator_sec_uid=None, tag=None, limit=20):
        return [self._video_row()], 1

    def get_video(self, video_db_id):
        if video_db_id != 7:
            return None
        return {
            **self._video_row(),
            "audio_path": "/data/audio/douyin/creator-1/video-1.wav",
            "audio_size": 2048,
            "transcript_text": "完整转写文本",
            "segments_json": json.dumps(
                [{"start": 0.0, "end": 1.5, "text": "第一段"}],
                ensure_ascii=False,
            ),
            "language": "zh",
            "transcription_model": "large-v3",
            "analysis_model": "deepseek-v4-flash",
        }

    @staticmethod
    def _video_row():
        return {
            "id": 7,
            "platform": "douyin",
            "video_id": "video-1",
            "creator_sec_uid": "creator-1",
            "creator_name": "创作者",
            "description": "视频描述",
            "source_create_time": 1_700_000_000,
            "status": "done",
            "updated_at": datetime(2026, 7, 13, 12, 0, 0),
            "summary": "视频摘要",
            "tags_json": json.dumps(["AI", "商业"], ensure_ascii=False),
            "key_points_json": json.dumps(["观点一"], ensure_ascii=False),
        }


class FrontendApiServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = FrontendService(FakeFrontendRepository())

    def test_dashboard_and_creator_models_use_frontend_contract(self) -> None:
        dashboard = self.service.dashboard().model_dump(by_alias=True)
        creators = self.service.creators(query=None, limit=20).model_dump(by_alias=True)

        self.assertEqual(dashboard["creatorCount"], 2)
        self.assertEqual(dashboard["statusCounts"]["done"], 3)
        self.assertEqual(dashboard["topTags"][0], {"tag": "AI", "count": 2})
        self.assertEqual(creators["items"][0]["secUid"], "creator-1")
        self.assertEqual(creators["items"][0]["topTags"], ["AI", "商业"])

    def test_video_detail_contains_transcript_segments_and_audio_url(self) -> None:
        detail = self.service.video_detail(7)
        assert detail is not None
        payload = detail.model_dump(by_alias=True)

        self.assertEqual(payload["transcript"], "完整转写文本")
        self.assertEqual(payload["segments"][0]["text"], "第一段")
        self.assertEqual(payload["audioUrl"], "/api/videos/7/audio")
        self.assertEqual(payload["transcriptionModel"], "large-v3")

    def test_missing_creator_and_video_return_none(self) -> None:
        self.assertIsNone(self.service.creator_detail("missing", limit=20))
        self.assertIsNone(self.service.video_detail(999))


if __name__ == "__main__":
    unittest.main()
