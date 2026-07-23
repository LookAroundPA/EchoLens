"""HTTP contract tests for topic intelligence endpoints."""

from datetime import datetime
import unittest

from fastapi.testclient import TestClient

from echolens.api.app import create_app
from echolens.api.dependencies import get_intelligence_api_service
from echolens.api.intelligence_models import (
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

    def test_missing_topic_and_invalid_window_are_rejected(self) -> None:
        missing = self.client.get("/api/intelligence/topics/999")
        invalid = self.client.get("/api/intelligence/topics", params={"windowDays": 14})

        self.assertEqual(missing.status_code, 404)
        self.assertEqual(invalid.status_code, 422)

    def test_openapi_exposes_intelligence_paths(self) -> None:
        paths = self.client.get("/openapi.json").json()["paths"]
        self.assertIn("/api/intelligence/topics", paths)
        self.assertIn("/api/intelligence/topics/{topic_id}", paths)
        self.assertIn("/api/intelligence/topics/{topic_id}/history", paths)


if __name__ == "__main__":
    unittest.main()
