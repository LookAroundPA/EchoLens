"""Tests for explainable topic heat and traceable opinion history."""

from datetime import datetime
import unittest

from echolens.api.intelligence_service import IntelligenceApiService


NOW = datetime(2026, 7, 23, 12, 0, 0)


def opinion_row(
    row_id: int,
    topic_id: int,
    creator_id: int,
    published_at: datetime,
    *,
    stance: str = "bullish",
    source_type: str = "explicit",
    name: str = "人工智能",
) -> dict:
    return {
        "id": row_id,
        "topic_id": topic_id,
        "creator_id": creator_id,
        "stance": stance,
        "source_type": source_type,
        "published_at": published_at,
        "canonical_name": name,
        "topic_type": "industry",
        "topic_status": "active",
    }


class FakeIntelligenceQueryRepository:
    def __init__(self) -> None:
        self.opinions = [
            opinion_row(1, 1, 1, datetime(2026, 7, 10), stance="neutral"),
            opinion_row(2, 1, 1, datetime(2026, 7, 17), stance="bullish"),
            opinion_row(
                3,
                1,
                1,
                datetime(2026, 7, 17, 18),
                stance="bullish",
                source_type="inferred",
            ),
            opinion_row(4, 1, 2, datetime(2026, 7, 18), stance="cautious"),
            opinion_row(
                5,
                1,
                3,
                datetime(2026, 7, 19),
                stance="bearish",
                source_type="inferred",
            ),
            opinion_row(6, 2, 4, datetime(2026, 7, 20), name="房地产"),
            opinion_row(7, 3, 5, datetime(2026, 7, 12), name="半导体"),
            opinion_row(8, 4, 6, datetime(2026, 7, 13), name="消费"),
            opinion_row(9, 4, 7, datetime(2026, 7, 14), name="消费"),
        ]
        self.changes = [
            {"id": 1, "topic_id": 1, "creator_id": 1, "change_type": "first_attention", "detected_at": datetime(2026, 7, 10)},
            {"id": 2, "topic_id": 1, "creator_id": 1, "change_type": "strengthened", "detected_at": datetime(2026, 7, 17)},
            {"id": 3, "topic_id": 1, "creator_id": 2, "change_type": "first_attention", "detected_at": datetime(2026, 7, 18)},
        ]

    def list_opinions_between(self, start, end, **kwargs):
        topic_id = kwargs.get("topic_id")
        return [
            row
            for row in self.opinions
            if start <= row["published_at"] < end
            and (topic_id is None or row["topic_id"] == topic_id)
        ]

    def list_changes_between(self, start, end, **kwargs):
        topic_id = kwargs.get("topic_id")
        return [
            row
            for row in self.changes
            if start <= row["detected_at"] < end
            and (topic_id is None or row["topic_id"] == topic_id)
        ]

    def get_topic(self, topic_id):
        if topic_id == 999:
            return None
        return {
            "id": topic_id,
            "canonical_name": "人工智能",
            "topic_type": "industry",
            "status": "active",
        }

    def list_aliases(self, topic_id):
        return ["人工智能", "AI"]

    def list_topic_opinions(self, topic_id, **kwargs):
        return [], 0

    def list_topic_changes(self, topic_id, **kwargs):
        return []


class IntelligenceApiServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = IntelligenceApiService(FakeIntelligenceQueryRepository())

    def test_radar_deduplicates_creator_stance_and_caps_same_day_mentions(self) -> None:
        response = self.service.radar(
            window_days=7,
            topic_status="all",
            topic_type=None,
            trend_filter="all",
            limit=10,
            now=NOW,
        )

        self.assertEqual(response.total, 4)
        ai = response.items[0]
        self.assertEqual(ai.topic.name, "人工智能")
        self.assertEqual(ai.metrics.opinion_count, 4)
        self.assertEqual(ai.metrics.creator_count, 3)
        self.assertEqual(ai.metrics.explicit_count, 2)
        self.assertEqual(ai.metrics.inferred_count, 2)
        self.assertEqual(ai.metrics.stance_counts["bullish"], 1)
        self.assertEqual(ai.metrics.stance_counts["cautious"], 1)
        self.assertEqual(ai.metrics.stance_counts["bearish"], 1)
        self.assertEqual(ai.metrics.weighted_mentions, 3.1)
        self.assertEqual(
            ai.metrics.heat_components,
            {"creator_score": 9.0, "mention_score": 3.1, "change_score": 3.0},
        )
        self.assertEqual(ai.metrics.heat_score, 15.1)
        self.assertEqual(ai.metrics.previous_heat_score, 5.5)
        self.assertEqual(ai.metrics.trend, "rising")
        self.assertEqual(ai.metrics.dominant_stance, "mixed")
        self.assertEqual(ai.metrics.consensus_ratio, 0.3333)
        cooled = next(item for item in response.items if item.topic.name == "半导体")
        self.assertEqual(cooled.metrics.opinion_count, 0)
        self.assertEqual(cooled.metrics.previous_heat_score, 4.0)
        self.assertEqual(cooled.metrics.trend, "falling")

    def test_radar_can_filter_to_falling_topics(self) -> None:
        response = self.service.radar(
            window_days=7,
            topic_status="all",
            topic_type=None,
            trend_filter="falling",
            limit=10,
            now=NOW,
        )

        self.assertEqual(response.total, 2)
        self.assertEqual(response.items[0].topic.name, "消费")
        self.assertEqual(response.items[0].metrics.previous_heat_score, 8.0)
        self.assertEqual(response.items[1].topic.name, "半导体")
        self.assertEqual(response.items[1].metrics.heat_score, 0.0)

    def test_topic_detail_returns_zero_current_metrics_for_old_topic(self) -> None:
        detail = self.service.topic_detail(1, window_days=7, opinion_limit=10, now=datetime(2026, 8, 23))

        self.assertIsNotNone(detail)
        assert detail is not None
        self.assertEqual(detail.topic.name, "人工智能")
        self.assertEqual(detail.aliases, ["人工智能", "AI"])
        self.assertEqual(detail.metrics.opinion_count, 0)
        self.assertEqual(detail.metrics.heat_score, 0.0)

    def test_missing_topic_returns_none(self) -> None:
        self.assertIsNone(
            self.service.topic_history(
                999,
                creator_sec_uid=None,
                limit=20,
                offset=0,
            )
        )


if __name__ == "__main__":
    unittest.main()
