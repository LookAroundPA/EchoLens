from __future__ import annotations

from datetime import datetime, timezone
import json
import unittest

from echolens.api.creator_profile import build_creator_profile


def video_row(
    video_id: int,
    *,
    point: str,
    segment_text: str,
    tags: list[str],
    created_at: int,
) -> dict:
    return {
        "id": video_id,
        "platform": "douyin",
        "video_id": f"source-{video_id}",
        "creator_sec_uid": "creator-1",
        "creator_name": "创作者",
        "description": f"视频 {video_id}",
        "source_create_time": created_at,
        "status": "done",
        "updated_at": datetime(2026, 7, 14, tzinfo=timezone.utc),
        "summary": f"摘要 {video_id}",
        "tags_json": json.dumps(tags, ensure_ascii=False),
        "key_points_json": json.dumps([point], ensure_ascii=False),
        "segments_json": json.dumps(
            [
                {"start": 3.0, "end": 8.0, "text": segment_text},
                {"start": 8.0, "end": 12.0, "text": "后续补充说明"},
            ],
            ensure_ascii=False,
        ),
    }


class CreatorProfileTests(unittest.TestCase):
    def test_merges_similar_points_and_keeps_video_sources(self) -> None:
        rows = [
            video_row(
                8,
                point="人工智能可以减少重复劳动",
                segment_text="人工智能可以减少重复劳动",
                tags=["AI", "效率"],
                created_at=1_720_000_000,
            ),
            video_row(
                7,
                point="人工智能减少重复劳动",
                segment_text="人工智能减少重复劳动",
                tags=["AI", "工作方法"],
                created_at=1_710_000_000,
            ),
        ]

        profile = build_creator_profile("创作者", rows)
        payload = profile.model_dump(by_alias=True)

        self.assertEqual(payload["analyzedVideoCount"], 2)
        self.assertEqual(payload["mainThemes"][0], {"tag": "AI", "count": 2})
        self.assertEqual(payload["insights"][0]["occurrenceCount"], 2)
        self.assertEqual(
            {source["videoId"] for source in payload["insights"][0]["sources"]},
            {7, 8},
        )
        self.assertEqual(payload["insights"][0]["sources"][0]["start"], 3.0)
        self.assertIn("AI", payload["overview"])

    def test_representative_video_prefers_richer_content(self) -> None:
        rich = video_row(
            12,
            point="把时间投入到判断和创造",
            segment_text="把时间投入到判断和创造",
            tags=["AI", "效率", "创造力"],
            created_at=1_700_000_000,
        )
        sparse = video_row(
            13,
            point="简短观点",
            segment_text="不相关内容",
            tags=[],
            created_at=1_730_000_000,
        )
        sparse["summary"] = None

        profile = build_creator_profile("创作者", [sparse, rich])

        self.assertEqual(profile.representative_videos[0].id, 12)
        self.assertIn("覆盖 AI、效率、创造力", profile.representative_videos[0].reason)

    def test_empty_profile_has_clear_fallback(self) -> None:
        profile = build_creator_profile("创作者", [])

        self.assertEqual(profile.analyzed_video_count, 0)
        self.assertEqual(profile.insights, [])
        self.assertIn("尚无已完成", profile.overview)


if __name__ == "__main__":
    unittest.main()
