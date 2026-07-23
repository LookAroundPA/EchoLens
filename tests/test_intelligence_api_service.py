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

    def list_topic_assets(self, topic_id):
        return [
            {
                "id": 30,
                "topic_id": topic_id,
                "relation_type": "benchmark",
                "note": "跟踪主题表现",
                "source": "manual",
                "created_at": datetime(2026, 7, 23),
                "updated_at": datetime(2026, 7, 23),
                "asset_id": 10,
                "asset_type": "etf",
                "code": "588000",
                "name": "科创50ETF",
                "market": "SH",
                "asset_status": "active",
            }
        ]

    def list_topic_changes(self, topic_id, **kwargs):
        return []

    def get_creator(self, creator_sec_uid):
        if creator_sec_uid == "missing":
            return None
        return {
            "id": 1,
            "platform": "douyin",
            "sec_uid": creator_sec_uid,
            "creator_name": "测试博主",
        }

    def list_creator_opinions(self, creator_sec_uid):
        return [
            {
                "id": 12,
                "topic_id": 1,
                "canonical_name": "人工智能",
                "topic_type": "industry",
                "topic_status": "active",
                "video_id": 22,
                "platform_video_id": "video-22",
                "video_description": "AI 行业更新",
                "raw_subject": "AI产业",
                "stance": "bullish",
                "source_type": "explicit",
                "time_horizon": "medium_term",
                "confidence": "high",
                "conclusion": "继续看好产业趋势",
                "reasoning_json": '["需求增长"]',
                "risks_json": '["估值偏高"]',
                "evidence_quote": "产业趋势仍然向上",
                "published_at": datetime(2026, 7, 22),
                "change_type": "strengthened",
                "change_summary": "由谨慎转为看多",
            },
            {
                "id": 11,
                "topic_id": 1,
                "canonical_name": "人工智能",
                "topic_type": "industry",
                "topic_status": "active",
                "video_id": 21,
                "platform_video_id": "video-21",
                "video_description": "AI 估值讨论",
                "raw_subject": "人工智能",
                "stance": "cautious",
                "source_type": "inferred",
                "time_horizon": "short_term",
                "confidence": "medium",
                "conclusion": "短期注意估值",
                "reasoning_json": "[]",
                "risks_json": "[]",
                "evidence_quote": None,
                "published_at": datetime(2026, 7, 10),
                "change_type": "first_attention",
                "change_summary": "首次关注人工智能",
            },
            {
                "id": 10,
                "topic_id": 2,
                "canonical_name": "黄金",
                "topic_type": "commodity",
                "topic_status": "pending",
                "video_id": 20,
                "platform_video_id": "video-20",
                "video_description": "黄金观点",
                "raw_subject": "黄金",
                "stance": "neutral",
                "source_type": "explicit",
                "time_horizon": "long_term",
                "confidence": "medium",
                "conclusion": "长期中性",
                "reasoning_json": "[]",
                "risks_json": "[]",
                "evidence_quote": "当前位置保持观察",
                "published_at": datetime(2026, 7, 1),
                "change_type": "first_attention",
                "change_summary": "首次关注黄金",
            },
        ]

    def list_creator_changes(self, creator_sec_uid):
        return [
            {
                "id": 40,
                "topic_id": 1,
                "canonical_name": "人工智能",
                "topic_type": "industry",
                "topic_status": "active",
                "current_opinion_id": 12,
                "current_video_id": 22,
                "change_type": "strengthened",
                "previous_stance": "cautious",
                "current_stance": "bullish",
                "change_summary": "由谨慎转为看多",
                "detected_at": datetime(2026, 7, 22),
            },
            {
                "id": 39,
                "topic_id": 2,
                "canonical_name": "黄金",
                "topic_type": "commodity",
                "topic_status": "pending",
                "current_opinion_id": 10,
                "current_video_id": 20,
                "change_type": "first_attention",
                "previous_stance": None,
                "current_stance": "neutral",
                "change_summary": "首次关注黄金",
                "detected_at": datetime(2026, 7, 1),
            },
        ]


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

    def test_creator_intelligence_summarizes_topics_and_traceable_changes(self) -> None:
        response = self.service.creator_intelligence(
            "creator-1",
            topic_limit=1,
            opinion_limit=2,
            change_limit=1,
        )

        self.assertIsNotNone(response)
        assert response is not None
        self.assertEqual(response.creator.name, "测试博主")
        self.assertEqual(response.topic_count, 2)
        self.assertEqual(len(response.topics), 1)
        self.assertEqual(response.opinion_count, 3)
        self.assertEqual(response.explicit_count, 2)
        self.assertEqual(response.inferred_count, 1)
        self.assertEqual(response.change_count, 2)
        self.assertEqual(response.topics[0].topic.name, "人工智能")
        self.assertEqual(response.topics[0].current_stance, "bullish")
        self.assertEqual(response.topics[0].opinion_count, 2)
        self.assertEqual(response.topics[0].change_count, 1)
        self.assertEqual(response.recent_opinions[0].evidence_quote, "产业趋势仍然向上")
        self.assertEqual(response.recent_changes[0].previous_stance, "cautious")

    def test_missing_topic_or_creator_returns_none(self) -> None:
        self.assertIsNone(
            self.service.topic_history(
                999,
                creator_sec_uid=None,
                limit=20,
                offset=0,
            )
        )
        self.assertIsNone(
            self.service.creator_intelligence(
                "missing",
                topic_limit=24,
                opinion_limit=20,
                change_limit=20,
            )
        )


if __name__ == "__main__":
    unittest.main()
