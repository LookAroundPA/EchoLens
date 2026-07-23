"""Tests for controlled topic review and merge service contracts."""

from datetime import datetime
import unittest

from echolens.api.intelligence_management_service import IntelligenceManagementService


class FakeManagementRepository:
    def __init__(self) -> None:
        self.rows = {
            1: {
                "id": 1,
                "canonical_name": "AI行业",
                "topic_type": "industry",
                "status": "pending",
                "aliases": ["AI行业"],
                "opinion_count": 2,
                "creator_count": 1,
                "latest_published_at": datetime(2026, 7, 20),
            },
            2: {
                "id": 2,
                "canonical_name": "人工智能",
                "topic_type": "industry",
                "status": "active",
                "aliases": ["人工智能", "AI"],
                "opinion_count": 8,
                "creator_count": 4,
                "latest_published_at": datetime(2026, 7, 22),
            },
        }
        self.last_list_args = None

    def list_topics(self, **kwargs):
        self.last_list_args = kwargs
        return list(self.rows.values()), len(self.rows)

    def get_topic_item(self, topic_id):
        return self.rows.get(topic_id)

    def update_topic(self, topic_id, *, canonical_name, status):
        self.rows[topic_id]["canonical_name"] = canonical_name
        self.rows[topic_id]["status"] = status
        self.rows[topic_id]["aliases"] = [canonical_name, *self.rows[topic_id]["aliases"]]

    def add_alias(self, topic_id, alias):
        self.rows[topic_id]["aliases"].append(alias)

    def merge_topics(self, source_topic_id, target_topic_id):
        moved = self.rows[source_topic_id]["opinion_count"]
        self.rows[target_topic_id]["opinion_count"] += moved
        self.rows[target_topic_id]["aliases"].extend(self.rows[source_topic_id]["aliases"])
        del self.rows[source_topic_id]
        return moved


class IntelligenceManagementServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = FakeManagementRepository()
        self.service = IntelligenceManagementService(self.repository)

    def test_lists_full_review_catalog(self) -> None:
        response = self.service.list_topics(
            status="pending",
            topic_type="industry",
            query="AI",
            limit=20,
            offset=0,
        )

        self.assertEqual(response.total, 2)
        self.assertEqual(response.items[0].topic.name, "AI行业")
        self.assertEqual(response.items[1].creator_count, 4)
        self.assertEqual(
            self.repository.last_list_args,
            {
                "status": "pending",
                "topic_type": "industry",
                "query": "AI",
                "limit": 20,
                "offset": 0,
            },
        )

    def test_updates_topic_and_adds_alias(self) -> None:
        updated = self.service.update_topic(1, canonical_name="人工智能行业", status="active")
        aliased = self.service.add_alias(1, "AI产业")

        self.assertIsNotNone(updated)
        self.assertEqual(updated.topic.status, "active")
        self.assertIsNotNone(aliased)
        self.assertIn("AI产业", aliased.aliases)

    def test_merges_source_into_target(self) -> None:
        response = self.service.merge_topics(1, 2)

        self.assertIsNotNone(response)
        assert response is not None
        self.assertEqual(response.source_topic_id, 1)
        self.assertEqual(response.moved_opinion_count, 2)
        self.assertEqual(response.target.opinion_count, 10)
        self.assertIn("AI行业", response.target.aliases)

    def test_missing_source_returns_none_and_missing_target_raises(self) -> None:
        self.assertIsNone(self.service.update_topic(999, canonical_name="缺失", status="active"))
        with self.assertRaises(KeyError):
            self.service.merge_topics(1, 999)


if __name__ == "__main__":
    unittest.main()
