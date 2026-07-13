"""HTTP contract tests for the frontend API routes."""

from datetime import datetime
import unittest

from fastapi.testclient import TestClient

from echolens.api.app import create_app
from echolens.api.dependencies import (
    get_frontend_service,
    get_management_repository,
    get_management_service,
    get_operation_service,
)
from echolens.api.models import (
    CreatorDetailResponse,
    CreatorListResponse,
    CreatorSummary,
    DashboardResponse,
    JobListResponse,
    JobStatus,
    ProcessingJob,
    SearchResponse,
    TagCount,
    TagListResponse,
    VideoDetail,
    VideoListResponse,
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


class FakeManagementService:
    def videos(self, **kwargs) -> VideoListResponse:
        return VideoListResponse(items=[], total=4)

    def tags(self, **kwargs) -> TagListResponse:
        return TagListResponse(items=[TagCount(tag="AI", count=3)])


class FakeManagementRepository:
    def get_video_state(self, video_db_id):
        if video_db_id == 999:
            return None
        return {"id": video_db_id, "status": "done"}


class FakeOperationService:
    def __init__(self) -> None:
        self.executed: list[tuple[int, str, dict]] = []

    @staticmethod
    def _job(job_id=1, job_type="scan", video_id=None) -> ProcessingJob:
        now = datetime(2026, 7, 13, 12, 0, 0)
        return ProcessingJob(
            id=job_id,
            video_id=video_id,
            job_type=job_type,
            status=JobStatus.queued,
            created_at=now,
            updated_at=now,
        )

    def create_job(self, job_type, payload, video_id=None) -> ProcessingJob:
        return self._job(job_id=7, job_type=job_type, video_id=video_id)

    def run_job(self, job_id, job_type, payload) -> None:
        self.executed.append((job_id, job_type, payload))

    def get_job(self, job_id):
        return None if job_id == 999 else self._job(job_id=job_id)

    def list_jobs(self, **kwargs) -> JobListResponse:
        return JobListResponse(items=[self._job()], total=1)


class FrontendApiRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        app = create_app(Settings(api_cors_origins="http://localhost:5173"))
        self.operation_service = FakeOperationService()
        app.dependency_overrides[get_frontend_service] = lambda: FakeFrontendService()
        app.dependency_overrides[get_management_service] = lambda: FakeManagementService()
        app.dependency_overrides[get_management_repository] = lambda: FakeManagementRepository()
        app.dependency_overrides[get_operation_service] = lambda: self.operation_service
        self.client = TestClient(app)

    def test_health_dashboard_video_list_and_tags_contract(self) -> None:
        health = self.client.get("/health")
        dashboard = self.client.get("/api/dashboard")
        videos = self.client.get("/api/videos")
        tags = self.client.get("/api/tags")

        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json(), {"status": "ok"})
        self.assertEqual(dashboard.json()["creatorCount"], 1)
        self.assertEqual(videos.json()["total"], 4)
        self.assertEqual(tags.json()["items"][0], {"tag": "AI", "count": 3})

    def test_creator_video_and_job_not_found(self) -> None:
        creator = self.client.get("/api/creators/missing")
        video = self.client.get("/api/videos/999")
        job = self.client.get("/api/jobs/999")

        self.assertEqual(creator.status_code, 404)
        self.assertEqual(video.status_code, 404)
        self.assertEqual(job.status_code, 404)

    def test_scan_pipeline_and_video_actions_return_jobs(self) -> None:
        scan = self.client.post("/api/actions/scan", json={"enqueue": True})
        pipeline = self.client.post(
            "/api/actions/pipeline",
            json={"scan": True, "maxTasks": 2},
        )
        video = self.client.post(
            "/api/videos/7/actions/process",
            json={"stage": "analysis", "continueToDone": True},
        )

        self.assertEqual(scan.status_code, 202)
        self.assertEqual(pipeline.status_code, 202)
        self.assertEqual(video.status_code, 202)
        self.assertEqual(video.json()["videoId"], 7)
        self.assertEqual(
            [item[1] for item in self.operation_service.executed],
            ["scan", "pipeline", "video_process"],
        )

    def test_missing_video_action_is_rejected(self) -> None:
        response = self.client.post(
            "/api/videos/999/actions/process",
            json={"stage": "current"},
        )
        self.assertEqual(response.status_code, 404)

    def test_openapi_and_post_cors_are_available_for_frontend(self) -> None:
        docs = self.client.get("/openapi.json")
        preflight = self.client.options(
            "/api/actions/pipeline",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
            },
        )

        self.assertEqual(docs.status_code, 200)
        paths = docs.json()["paths"]
        self.assertIn("/api/actions/pipeline", paths)
        self.assertIn("post", paths["/api/actions/pipeline"])
        self.assertEqual(preflight.status_code, 200)
        self.assertEqual(
            preflight.headers["access-control-allow-origin"],
            "http://localhost:5173",
        )


if __name__ == "__main__":
    unittest.main()
