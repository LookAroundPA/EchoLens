"""Tests for deterministic creator opinion-change classification."""

import unittest

from echolens.intelligence.changes import detect_opinion_change


class OpinionChangeTests(unittest.TestCase):
    def test_first_mention(self) -> None:
        self.assertEqual(detect_opinion_change(None, "bullish"), "first_mention")

    def test_unchanged_stance_is_not_a_change(self) -> None:
        self.assertIsNone(detect_opinion_change("bullish", "bullish", gap_days=7))

    def test_long_gap_marks_resumed_attention(self) -> None:
        self.assertEqual(
            detect_opinion_change("bullish", "bullish", gap_days=120),
            "resumed_attention",
        )

    def test_bullish_to_bearish_is_reversal(self) -> None:
        self.assertEqual(detect_opinion_change("bullish", "bearish"), "reversal")

    def test_bullish_to_strong_bullish_is_strengthened(self) -> None:
        self.assertEqual(
            detect_opinion_change("bullish", "strong_bullish"),
            "strengthened",
        )

    def test_strong_bearish_to_bearish_is_weakened(self) -> None:
        self.assertEqual(
            detect_opinion_change("strong_bearish", "bearish"),
            "weakened",
        )

    def test_directional_to_cautious_is_explicit(self) -> None:
        self.assertEqual(
            detect_opinion_change("bullish", "cautious"),
            "became_cautious",
        )


if __name__ == "__main__":
    unittest.main()
