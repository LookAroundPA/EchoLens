"""Tests for historical intelligence rebuild parsing."""

import json
import unittest

from echolens.intelligence.service import IntelligenceService


VALID_INSIGHT = {
    "subject": "人工智能",
    "subject_type": "industry",
    "stance": "bullish",
    "conclusion": "产业趋势仍然向上",
    "source_type": "explicit",
    "time_horizon": "medium_term",
    "confidence": "high",
    "reasoning": ["需求增长"],
    "risks": ["估值过高"],
    "evidence_quote": "仍然看好人工智能",
}


class IntelligenceServiceTests(unittest.TestCase):
    def test_parses_stored_json(self) -> None:
        insights, invalid = IntelligenceService._parse_insights(
            json.dumps([VALID_INSIGHT], ensure_ascii=False)
        )
        self.assertEqual(invalid, 0)
        self.assertEqual(len(insights), 1)
        self.assertEqual(insights[0].subject, "人工智能")

    def test_rejects_malformed_json_without_raising(self) -> None:
        insights, invalid = IntelligenceService._parse_insights("{")
        self.assertEqual(insights, [])
        self.assertEqual(invalid, 1)

    def test_counts_invalid_items(self) -> None:
        insights, invalid = IntelligenceService._parse_insights([VALID_INSIGHT, {"subject": "AI"}])
        self.assertEqual(len(insights), 1)
        self.assertEqual(invalid, 1)


if __name__ == "__main__":
    unittest.main()
