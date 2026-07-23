"""Tests for deterministic investment-topic normalization."""

import unittest

from echolens.intelligence.normalization import find_seed_topic, normalize_topic_name


class TopicNormalizationTests(unittest.TestCase):
    def test_normalizes_width_case_and_punctuation(self) -> None:
        self.assertEqual(normalize_topic_name(" ＡＩ-产业链 "), "ai产业链")

    def test_ai_aliases_resolve_to_one_seed_topic(self) -> None:
        for subject in (
            "人工智能",
            "AI",
            "AI产业",
            "AI行业",
            "AI产业链",
            "人工智能产业链",
            "中国AI产业",
        ):
            with self.subTest(subject=subject):
                topic = find_seed_topic(subject, "industry")
                self.assertIsNotNone(topic)
                assert topic is not None
                self.assertEqual(topic.canonical_name, "人工智能")

    def test_market_aliases_resolve_to_one_seed_topic(self) -> None:
        for subject in ("A股", "A股市场", "A股市场整体", "中国A股"):
            with self.subTest(subject=subject):
                topic = find_seed_topic(subject, "market")
                self.assertIsNotNone(topic)
                assert topic is not None
                self.assertEqual(topic.canonical_name, "A股")

    def test_alias_does_not_cross_topic_types(self) -> None:
        self.assertIsNone(find_seed_topic("AI", "stock"))


if __name__ == "__main__":
    unittest.main()
