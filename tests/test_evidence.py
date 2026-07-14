from __future__ import annotations

import json
import unittest

from echolens.api.evidence import key_point_evidence, search_match
from echolens.api.models import TranscriptSegment


class EvidenceMatchingTests(unittest.TestCase):
    def test_search_returns_timestamped_segment_window(self) -> None:
        row = {
            "description": "普通描述",
            "summary": "普通摘要",
            "transcript_text": "先讨论准备工作，随后介绍人工智能如何帮助学习。",
            "segments_json": json.dumps(
                [
                    {"start": 0.0, "end": 4.0, "text": "先讨论准备工作"},
                    {"start": 4.0, "end": 8.0, "text": "随后介绍人工智能"},
                    {"start": 8.0, "end": 12.0, "text": "如何帮助学习"},
                ],
                ensure_ascii=False,
            ),
            "tags_json": "[]",
            "key_points_json": "[]",
        }

        match = search_match(row, "人工智能如何")

        self.assertEqual(match.match_type, "transcript")
        self.assertEqual(match.start, 4.0)
        self.assertEqual(match.end, 12.0)
        self.assertEqual(match.segment_index, 1)
        self.assertEqual(match.segment_count, 2)

    def test_search_falls_back_to_summary_without_fake_timestamp(self) -> None:
        match = search_match(
            {
                "description": "",
                "summary": "这是一段商业模式总结",
                "transcript_text": "",
                "segments_json": "[]",
                "tags_json": "[]",
                "key_points_json": "[]",
            },
            "商业模式",
        )

        self.assertEqual(match.match_type, "summary")
        self.assertIsNone(match.start)
        self.assertIn("商业模式", match.text)

    def test_key_point_links_to_best_neighboring_segments(self) -> None:
        segments = [
            TranscriptSegment(start=0, end=5, text="前面先说明背景信息"),
            TranscriptSegment(start=5, end=10, text="人工智能可以减少重复劳动"),
            TranscriptSegment(start=10, end=15, text="让人把时间投入到判断和创造"),
        ]

        matches = key_point_evidence(
            ["人工智能减少重复劳动，让人专注判断和创造"],
            segments,
        )

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].segment_index, 1)
        self.assertEqual(matches[0].segment_count, 2)
        self.assertEqual(matches[0].start, 5)
        self.assertEqual(matches[0].end, 15)


if __name__ == "__main__":
    unittest.main()
