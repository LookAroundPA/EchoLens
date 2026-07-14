"""Tests for submitting frontend operations to Redis."""

from datetime import datetime
import unittest

from echolens.api.models import JobStatus, ProcessingJob
from echolens.api.queued_operations import JobQueueUnavailable, QueuedOperationService
from echolens.core.config import Settings


def make_job() -> ProcessingJob:
    now = datetime(2026, 7, 14, 12, 0, 0)
    return ProcessingJob(
        id=31,
        job_type="pipeline",
        status=JobStatus.queued,
        payload={"scan": True, "maxTasks": 5},
        created_at=now,
        updated_at=now,
    )


class FakeQueue:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.messages: list[tuple[int, str, dict]] = []

    def push(self, *, job_id: int, job_type: str, payload: dict) -> int:
        if self.fail:
            raise ConnectionError("redis unavailable")
        self.messages.append((job_id, job_type, payload))
        return len(self.messages)


class RecordingQueuedOperationService(QueuedOperationService):
    def __init__(self, queue: FakeQueue) -> None:
        super().__init__(settings=Settings(), queue=queue)
        self.failed: list[tuple[int, str]] = []

    def _mark_failed(self, job_id: int, error_message: str) -> None:
        self.failed.append((job_id, error_message))


class QueuedOperationServiceTests(unittest.TestCase):
    def test_enqueues_existing_job_message(self) -> None:
        queue = FakeQueue()
        service = RecordingQueuedOperationService(queue)
        job = make_job()

        service.enqueue_job(job)

        self.assertEqual(
            queue.messages,
            [(31, "pipeline", {"scan": True, "maxTasks": 5})],
        )
        self.assertEqual(service.failed, [])

    def test_marks_job_failed_when_redis_is_unavailable(self) -> None:
        service = RecordingQueuedOperationService(FakeQueue(fail=True))

        with self.assertRaisesRegex(JobQueueUnavailable, "Redis operation queue"):
            service.enqueue_job(make_job())

        self.assertEqual(
            service.failed,
            [(31, "Redis operation queue is unavailable")],
        )


if __name__ == "__main__":
    unittest.main()
