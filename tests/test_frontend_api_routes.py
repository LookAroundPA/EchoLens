"""HTTP contract tests for the frontend API routes."""

import unittest

from fastapi.testclient import TestClient

from echolens.api.app import create_app
from echolens.api.dependencies import get_frontend_service
from echolens.api.models import (
    CreatorDetailResponse,
    CreatorListResponse,
    CreatorSummary,
    DashboardResponse,
    SearchResponse,
    VideoDetail,
)
from echolens.core.config import Settings


class FakeFrontendService:
    def dashboard(self) -> DashboardResponse:
        return DashboardResponse(
            creator_count=1,
            video_count=1,
            completed_count=1,
            status_counts={"done": 1},
            top_tags=[],
            recent_videos=[],
        )

    def creators(self, query, limit) -> CreatorListResponse:
        return CreatorListResponse(
            items=[
                CreatorSummary(
                    platform="douyin",
                    sec_uid="creator-1",
                    name="创作者",
                    video_count=1,
                    completed_count=1,
                )
            ],
            total=1,
        )

    def creator_detail(self, sec_uid, limit):
        if sec_uid == "missing":
            return None
        return CreatorDetailResponse(
            creator=CreatorSummary(
                platform="douyin",
                sec_uid=sec_uid,
                name="创作者",
                video_count=1,
                completed_count=1,
            ),
            videos=[],
        )

    def video_detail(self, video_db_id):
        if video_db_id == 999:
            return None
        return VideoDetail(
            id=video_db_id,
            platform="douyin",
            video_id="video-1",
            creator_sec_uid="creator-1",
            creator_name="创作者",
            status="done",
            transcript="转写",
        )

    def search(self, query, creator_sec_uid, tag, limit) -> SearchResponse:
        return SearchResponse(items=[], total=0)


class FrontendApiRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        app = create_app(Settings(api_cors_origins="http://localhost:5173"))
        service = FakeFrontendService()
        app.dependency_overrides[get_frontend_service] = lambda: service
        self.client = TestClient(app)

    def test_health_and_dashboard_contract(self) -> None:
        health = self.client.get("/health")
        dashboard = self.client.get("/api/dashboard")

        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json(), {"status": "ok"})
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.json()["creatorCount"], 1)

    def test_creator_and_video_not_found(self) -> None:
        creator = self.client.get("/api/creators/missing")
        video = self.client.get("/api/videos/999")

        self.assertEqual(creator.status_code, 404)
        self.assertEqual(video.status_code, 404)

    def test_openapi_and_cors_are_available_for_frontend(self) -> None:
        docs = self.client.get("/openapi.json")
        preflight = self.client.options(
            "/api/dashboard",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )

        self.assertEqual(docs.status_code, 200)
        self.assertIn("/api/search", docs.json()["paths"])
        self.assertEqual(preflight.status_code, 200)
        self.assertEqual(
            preflight.headers["access-control-allow-origin"],
            "http://localhost:5173",
        )


if __name__ == "__main__":
    unittest.main()
