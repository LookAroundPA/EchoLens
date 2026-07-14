"""HTTP contract tests for retrying failed frontend jobs."""

from datetime import datetime
import unittest

from fastapi.testclient import TestClient

from echolens.api.app import create_app
from echolens.api.dependencies import get_operation_service
from echolens.api.job_retry import JobRetryConflict
from echolens.api.models import JobStatus, ProcessingJob
from echolens.api.retry_routes import get_job_retry_service
from echolens.core.config import Settings


class FakeRetryService:
    @staticmethod
    def _job() -> ProcessingJob:
        now = datetime(2026, 7, 14, 12, 0, 0)
        return ProcessingJob(
            id=17,
            job_type="pipeline",
            status=JobStatus.queued,
            retry_count=2,
            payload={"scan": False, "maxTasks": 3},
            created_at=now,
            updated_at=now,
        )

    def retry(self, job_id: int) -> ProcessingJob | None:
        if job_id == 404:
            return None
        if job_id == 9:
            raise JobRetryConflict("Only failed jobs can be retried; current status is running")
        return self._job()


class FakeOperationService:
    def __init__(self) -> None:
        self.enqueued: list[ProcessingJob] = []

    def enqueue_job(self, job: ProcessingJob) -> None:
        self.enqueued.append(job)


class JobRetryApiTests(unittest.TestCase):
    def setUp(self) -> None:
        app = create_app(Settings(api_cors_origins="http://localhost:5173"))
        self.operation_service = FakeOperationService()
        app.dependency_overrides[get_job_retry_service] = lambda: FakeRetryService()
        app.dependency_overrides[get_operation_service] = lambda: self.operation_service
        self.client = TestClient(app)

    def test_retry_creates_and_enqueues_new_job(self) -> None:
        response = self.client.post("/api/jobs/5/actions/retry")

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["id"], 17)
        self.assertEqual(response.json()["retryCount"], 2)
        self.assertEqual([job.id for job in self.operation_service.enqueued], [17])

    def test_missing_job_returns_not_found(self) -> None:
        response = self.client.post("/api/jobs/404/actions/retry")
        self.assertEqual(response.status_code, 404)

    def test_non_failed_job_returns_conflict(self) -> None:
        response = self.client.post("/api/jobs/9/actions/retry")
        self.assertEqual(response.status_code, 409)
        self.assertIn("Only failed jobs", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
