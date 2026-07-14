from __future__ import annotations

import unittest

from echolens.api.content_service import ContentService
from echolens.api.models import KeyPointEvidence, VideoDetail


class EvidenceExportTests(unittest.TestCase):
    def test_markdown_and_json_exports_keep_key_point_sources(self) -> None:
        service = object.__new__(ContentService)
        video = VideoDetail(
            id=7,
            platform="douyin",
            video_id="source-7",
            creator_sec_uid="creator-7",
            creator_name="创作者",
            description="测试视频",
            summary="摘要",
            tags=["AI"],
            key_points=["人工智能减少重复劳动"],
            status="done",
            transcript="完整转写",
            key_point_evidence=[
                KeyPointEvidence(
                    key_point_index=0,
                    segment_index=2,
                    segment_count=1,
                    start=65.0,
                    end=73.0,
                    text="人工智能可以减少重复劳动",
                    score=0.91,
                )
            ],
        )

        markdown = service.export_markdown(video)
        exported_json = service.export_json(video)

        self.assertIn("人工智能减少重复劳动（来源 1:05–1:13）", markdown)
        self.assertEqual(exported_json["keyPointEvidence"][0]["segmentIndex"], 2)
        self.assertEqual(exported_json["keyPointEvidence"][0]["start"], 65.0)


if __name__ == "__main__":
    unittest.main()
