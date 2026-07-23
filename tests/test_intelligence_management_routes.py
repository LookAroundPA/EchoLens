"""HTTP contract tests for topic review and merge endpoints."""

from datetime import datetime
import unittest

from fastapi.testclient import TestClient

from echolens.api.app import create_app
from echolens.api.dependencies import get_intelligence_management_service
from echolens.api.intelligence_models import (
    ReferenceAsset,
    ReferenceAssetListResponse,
    TopicAssetListResponse,
    TopicAssetMapping,
    TopicMergeResponse,
    TopicReviewItem,
    TopicReviewListResponse,
    TopicSummary,
)
from echolens.core.config import Settings


class FakeManagementService:
    def __init__(self) -> None:
        self.list_args = None
        self.update_args = None
        self.alias_args = None
        self.merge_args = None
        self.asset_args = None
        self.mapping_args = None
        self.conflict = False

    @staticmethod
    def item(topic_id=1, name="AI行业", status="pending") -> TopicReviewItem:
        return TopicReviewItem(
            topic=TopicSummary(id=topic_id, name=name, topic_type="industry", status=status),
            aliases=[name],
            opinion_count=2,
            creator_count=1,
            latest_published_at=datetime(2026, 7, 20),
        )

    @staticmethod
    def asset(asset_id=10) -> ReferenceAsset:
        return ReferenceAsset(
            id=asset_id,
            asset_type="etf",
            code="588000",
            name="科创50ETF",
            market="SH",
            status="active",
        )

    @classmethod
    def mapping(cls, topic_id=1) -> TopicAssetMapping:
        now = datetime(2026, 7, 23)
        return TopicAssetMapping(
            id=30,
            topic_id=topic_id,
            asset=cls.asset(),
            relation_type="benchmark",
            note="跟踪主题表现",
            source="manual",
            created_at=now,
            updated_at=now,
        )

    def list_topics(self, **kwargs):
        self.list_args = kwargs
        return TopicReviewListResponse(items=[self.item()], total=1)

    def list_assets(self, **kwargs):
        self.asset_args = kwargs
        return ReferenceAssetListResponse(items=[self.asset()], total=1)

    def create_asset(self, **kwargs):
        self.asset_args = kwargs
        return self.asset()

    def list_topic_assets(self, topic_id):
        if topic_id == 999:
            return None
        return TopicAssetListResponse(items=[self.mapping(topic_id)], total=1)

    def map_asset(self, topic_id, **kwargs):
        self.mapping_args = {"topic_id": topic_id, **kwargs}
        if topic_id == 999:
            return None
        if self.conflict:
            raise ValueError("Only active reviewed topics can have reference assets")
        return TopicAssetListResponse(items=[self.mapping(topic_id)], total=1)

    def remove_asset_mapping(self, topic_id, mapping_id):
        self.mapping_args = {"topic_id": topic_id, "mapping_id": mapping_id}
        if mapping_id == 999:
            raise KeyError("Asset mapping 999 does not exist")
        return TopicAssetListResponse(items=[], total=0)

    def update_topic(self, topic_id, **kwargs):
        self.update_args = {"topic_id": topic_id, **kwargs}
        if topic_id == 999:
            return None
        if self.conflict:
            raise ValueError("Topic name already exists")
        return self.item(topic_id, kwargs["canonical_name"], kwargs["status"])

    def add_alias(self, topic_id, alias):
        self.alias_args = {"topic_id": topic_id, "alias": alias}
        if topic_id == 999:
            return None
        if self.conflict:
            raise ValueError("Alias already belongs to another topic")
        item = self.item(topic_id)
        item.aliases.append(alias)
        return item

    def merge_topics(self, source_topic_id, target_topic_id):
        self.merge_args = {
            "source_topic_id": source_topic_id,
            "target_topic_id": target_topic_id,
        }
        if source_topic_id == 999:
            return None
        if target_topic_id == 999:
            raise KeyError("Topic 999 does not exist")
        if self.conflict:
            raise ValueError("Only topics of the same type can be merged")
        return TopicMergeResponse(
            source_topic_id=source_topic_id,
            moved_opinion_count=2,
            target=self.item(target_topic_id, "人工智能", "active"),
        )


class IntelligenceManagementRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        app = create_app(Settings(api_cors_origins="http://localhost:5173"))
        self.service = FakeManagementService()
        app.dependency_overrides[get_intelligence_management_service] = lambda: self.service
        self.client = TestClient(app)

    def test_lists_review_catalog_with_filters(self) -> None:
        response = self.client.get(
            "/api/intelligence/topic-review",
            params={"status": "pending", "type": "industry", "q": "AI", "limit": 20},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"][0]["topic"]["name"], "AI行业")
        self.assertEqual(
            self.service.list_args,
            {
                "status": "pending",
                "topic_type": "industry",
                "query": "AI",
                "limit": 20,
                "offset": 0,
            },
        )

    def test_asset_catalog_and_topic_mapping_contracts(self) -> None:
        catalog = self.client.get(
            "/api/intelligence/assets",
            params={"type": "etf", "q": "科创", "limit": 20},
        )
        created = self.client.post(
            "/api/intelligence/assets",
            json={"assetType": "etf", "code": "588000", "name": "科创50ETF", "market": "SH"},
        )
        mapped = self.client.post(
            "/api/intelligence/topics/1/assets",
            json={"assetId": 10, "relationType": "benchmark", "note": "跟踪主题表现"},
        )
        removed = self.client.post("/api/intelligence/topics/1/assets/30/remove")

        self.assertEqual(catalog.status_code, 200)
        self.assertEqual(catalog.json()["items"][0]["code"], "588000")
        self.assertEqual(created.status_code, 200)
        self.assertEqual(mapped.status_code, 200)
        self.assertEqual(mapped.json()["items"][0]["relationType"], "benchmark")
        self.assertEqual(removed.status_code, 200)
        self.assertEqual(removed.json()["total"], 0)
        self.assertEqual(self.service.mapping_args, {"topic_id": 1, "mapping_id": 30})

    def test_review_alias_and_merge_contracts(self) -> None:
        reviewed = self.client.patch(
            "/api/intelligence/topics/1/review",
            json={"canonicalName": "人工智能行业", "status": "active"},
        )
        aliased = self.client.post(
            "/api/intelligence/topics/1/aliases",
            json={"alias": "AI产业"},
        )
        merged = self.client.post(
            "/api/intelligence/topics/1/merge",
            json={"targetTopicId": 2},
        )

        self.assertEqual(reviewed.status_code, 200)
        self.assertEqual(reviewed.json()["topic"]["status"], "active")
        self.assertEqual(aliased.status_code, 200)
        self.assertIn("AI产业", aliased.json()["aliases"])
        self.assertEqual(merged.status_code, 200)
        self.assertEqual(merged.json()["movedOpinionCount"], 2)
        self.assertEqual(self.service.merge_args["target_topic_id"], 2)

    def test_missing_and_conflicting_mutations_are_mapped(self) -> None:
        missing = self.client.patch(
            "/api/intelligence/topics/999/review",
            json={"canonicalName": "缺失", "status": "active"},
        )
        missing_target = self.client.post(
            "/api/intelligence/topics/1/merge",
            json={"targetTopicId": 999},
        )
        self.service.conflict = True
        conflict = self.client.post(
            "/api/intelligence/topics/1/aliases",
            json={"alias": "冲突"},
        )

        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing_target.status_code, 404)
        self.assertEqual(conflict.status_code, 409)

    def test_openapi_exposes_management_paths(self) -> None:
        paths = self.client.get("/openapi.json").json()["paths"]
        self.assertIn("/api/intelligence/assets", paths)
        self.assertIn("/api/intelligence/topics/{topic_id}/assets", paths)
        self.assertIn("/api/intelligence/topics/{topic_id}/assets/{mapping_id}/remove", paths)
        self.assertIn("/api/intelligence/topic-review", paths)
        self.assertIn("/api/intelligence/topics/{topic_id}/review", paths)
        self.assertIn("/api/intelligence/topics/{topic_id}/aliases", paths)
        self.assertIn("/api/intelligence/topics/{topic_id}/merge", paths)


if __name__ == "__main__":
    unittest.main()
