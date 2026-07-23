"""HTTP contract tests for topic intelligence endpoints."""

from datetime import datetime
import unittest

from fastapi.testclient import TestClient

from echolens.api.app import create_app
from echolens.api.dependencies import get_intelligence_api_service
from echolens.api.intelligence_models import (
    CreatorIntelligenceIdentity,
    CreatorIntelligenceResponse,
    CreatorTopicHistorySummary,
    TopicDetailResponse,
    TopicHeatMetrics,
    TopicHistoryResponse,
    TopicOpinion,
    TopicRadarItem,
    TopicRadarResponse,
    TopicSummary,
)
from echolens.core.config import Settings


class FakeIntelligenceApiService:
    def __init__(self) -> None:
        self.radar_args = None
        self.history_args = None
        self.creator_args = None

    @staticmethod
    def _topic() -> TopicSummary:
        return TopicSummary(id=7, name="人工智能", topic_type="industry", status="active")

    @staticmethod
    def _metrics(window_days: int) -> TopicHeatMetrics:
        return TopicHeatMetrics(
            window_days=window_days,
            opinion_count=4,
            creator_count=3,
            stance_counts={"bullish": 2, "bearish": 1},
            bullish_ratio=0.6667,
            bearish_ratio=0.3333,
            dominant_stance="bullish",
            consensus_ratio=0.6667,
            weighted_mentions=3.5,
            heat_score=12.5,
            previous_heat_score=8.0,
            heat_change=4.5,
            trend="rising",
        )

    def radar(self, **kwargs) -> TopicRadarResponse:
        self.radar_args = kwargs
        return TopicRadarResponse(
            window_days=kwargs["window_days"],
            generated_at=datetime(2026, 7, 23, 12, 0, 0),
            items=[
                TopicRadarItem(
                    topic=self._topic(),
                    metrics=self._metrics(kwargs["window_days"]),
                    latest_published_at=datetime(2026, 7, 22),
                )
            ],
            total=1,
        )

    def topic_detail(self, topic_id, **kwargs):
        if topic_id == 999:
            return None
        return TopicDetailResponse(
            topic=self._topic(),
            aliases=["人工智能", "AI"],
            metrics=self._metrics(kwargs["window_days"]),
            latest_opinions=[],
            recent_changes=[],
        )

    def topic_history(self, topic_id, **kwargs):
        self.history_args = {"topic_id": topic_id, **kwargs}
        if topic_id == 999:
            return None
        return TopicHistoryResponse(
            topic=self._topic(),
            items=[
                TopicOpinion(
                    id=11,
                    topic_id=7,
                    creator_id=3,
                    creator_platform="douyin",
                    creator_sec_uid="creator-1",
                    creator_name="博主",
                    video_id=9,
                    platform_video_id="video-9",
                    raw_subject="AI产业链",
                    stance="bullish",
                    source_type="explicit",
                    time_horizon="short_term",
                    confidence="high",
                    conclusion="短期看多",
                    published_at=datetime(2026, 7, 22),
                )
            ],
            total=1,
        )

    def creator_intelligence(self, creator_sec_uid, **kwargs):
        self.creator_args = {"creator_sec_uid": creator_sec_uid, **kwargs}
        if creator_sec_uid == "missing":
            return None
        return CreatorIntelligenceResponse(
            creator=CreatorIntelligenceIdentity(
                id=3,
                platform="douyin",
                sec_uid=creator_sec_uid,
                name="博主",
            ),
            topic_count=1,
            opinion_count=2,
            explicit_count=1,
            inferred_count=1,
            change_count=1,
            topics=[
                CreatorTopicHistorySummary(
                    topic=self._topic(),
                    opinion_count=2,
                    explicit_count=1,
                    inferred_count=1,
                    change_count=1,
                    current_stance="bullish",
                    current_source_type="explicit",
                    current_time_horizon="short_term",
                    current_confidence="high",
                    latest_conclusion="继续看多",
                    latest_evidence_quote="产业趋势向上",
                    latest_opinion_id=11,
                    latest_video_id=9,
                    first_published_at=datetime(2026, 7, 1),
                    latest_published_at=datetime(2026, 7, 22),
                )
            ],
            recent_opinions=[],
            recent_changes=[],
        )


class IntelligenceApiRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        app = create_app(Settings(api_cors_origins="http://localhost:5173"))
        self.service = FakeIntelligenceApiService()
        app.dependency_overrides[get_intelligence_api_service] = lambda: self.service
        self.client = TestClient(app)

    def test_topic_radar_contract_and_filters(self) -> None:
        response = self.client.get(
            "/api/intelligence/topics",
            params={
                "windowDays": 30,
                "status": "active",
                "type": "industry",
                "trend": "falling",
                "limit": 20,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["windowDays"], 30)
        self.assertEqual(payload["items"][0]["topic"]["name"], "人工智能")
        self.assertEqual(payload["items"][0]["metrics"]["creatorCount"], 3)
        self.assertEqual(payload["items"][0]["metrics"]["trend"], "rising")
        self.assertEqual(
            self.service.radar_args,
            {
                "window_days": 30,
                "topic_status": "active",
                "topic_type": "industry",
                "trend_filter": "falling",
                "limit": 20,
            },
        )

    def test_topic_detail_and_creator_history_contract(self) -> None:
        detail = self.client.get("/api/intelligence/topics/7", params={"windowDays": 7})
        history = self.client.get(
            "/api/intelligence/topics/7/history",
            params={"creator": "creator-1", "limit": 10, "offset": 2},
        )

        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["aliases"], ["人工智能", "AI"])
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.json()["items"][0]["evidenceQuote"], None)
        self.assertEqual(
            self.service.history_args,
            {
                "topic_id": 7,
                "creator_sec_uid": "creator-1",
                "limit": 10,
                "offset": 2,
            },
        )

    def test_creator_intelligence_contract(self) -> None:
        response = self.client.get(
            "/api/intelligence/creators/creator-1",
            params={"topicLimit": 18, "opinionLimit": 12, "changeLimit": 8},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["creator"]["name"], "博主")
        self.assertEqual(payload["topics"][0]["currentStance"], "bullish")
        self.assertEqual(payload["topics"][0]["latestEvidenceQuote"], "产业趋势向上")
        self.assertEqual(
            self.service.creator_args,
            {
                "creator_sec_uid": "creator-1",
                "topic_limit": 18,
                "opinion_limit": 12,
                "change_limit": 8,
            },
        )

    def test_missing_topic_creator_and_invalid_window_are_rejected(self) -> None:
        missing = self.client.get("/api/intelligence/topics/999")
        missing_creator = self.client.get("/api/intelligence/creators/missing")
        invalid = self.client.get("/api/intelligence/topics", params={"windowDays": 14})

        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing_creator.status_code, 404)
        self.assertEqual(invalid.status_code, 422)

    def test_openapi_exposes_intelligence_paths(self) -> None:
        paths = self.client.get("/openapi.json").json()["paths"]
        self.assertIn("/api/intelligence/topics", paths)
        self.assertIn("/api/intelligence/creators/{creator_sec_uid}", paths)
        self.assertIn("/api/intelligence/topics/{topic_id}", paths)
        self.assertIn("/api/intelligence/topics/{topic_id}/history", paths)


if __name__ == "__main__":
    unittest.main()
