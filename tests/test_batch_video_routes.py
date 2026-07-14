"""HTTP contract tests for selected-video batch processing."""

from datetime import datetime
import unittest

from fastapi.testclient import TestClient

from echolens.api.app import create_app
from echolens.api.dependencies import get_management_repository, get_operation_service
from echolens.api.models import JobStatus, ProcessingJob
from echolens.core.config import Settings


class FakeManagementRepository:
    def get_video_state(self, video_db_id: int):
        if video_db_id == 404:
            return None
        return {"id": video_db_id, "status": "done"}


class FakeOperationService:
    def __init__(self) -> None:
        self.created: list[tuple[str, dict]] = []

    def create_job(self, *, job_type: str, payload: dict, video_id=None) -> ProcessingJob:
        self.created.append((job_type, payload))
        now = datetime(2026, 7, 14, 10, 0, 0)
        return ProcessingJob(
            id=21,
            job_type=job_type,
            status=JobStatus.queued,
            payload=payload,
            created_at=now,
            updated_at=now,
        )


class BatchVideoRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        app = create_app(Settings(api_cors_origins="http://localhost:5173"))
        self.operation_service = FakeOperationService()
        app.dependency_overrides[get_management_repository] = lambda: FakeManagementRepository()
        app.dependency_overrides[get_operation_service] = lambda: self.operation_service
        self.client = TestClient(app)

    def test_batch_action_deduplicates_and_creates_queued_job(self) -> None:
        response = self.client.post(
            "/api/videos/actions/batch-process",
            json={
                "videoIds": [3, 3, 7],
                "stage": "analysis",
                "continueToDone": True,
            },
        )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["jobType"], "video_batch")
        self.assertEqual(self.operation_service.created[0][1]["videoIds"], [3, 7])

    def test_batch_action_rejects_missing_video(self) -> None:
        response = self.client.post(
            "/api/videos/actions/batch-process",
            json={"videoIds": [3, 404], "stage": "current"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertIn("404", response.json()["detail"])
        self.assertEqual(self.operation_service.created, [])

    def test_batch_action_requires_at_least_one_video(self) -> None:
        response = self.client.post(
            "/api/videos/actions/batch-process",
            json={"videoIds": [], "stage": "current"},
        )

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
