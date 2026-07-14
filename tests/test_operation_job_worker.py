"""Tests for the independent Redis operation worker."""

from datetime import datetime
import unittest

from echolens.api.models import JobStatus, ProcessingJob
from echolens.operation_job_worker import OperationJobWorker
from echolens.storage.operation_queue import ReservedOperation


def make_job(status: JobStatus) -> ProcessingJob:
    now = datetime(2026, 7, 14, 12, 0, 0)
    return ProcessingJob(
        id=12,
        job_type="video_process",
        status=status,
        payload={"videoId": 7, "stage": "analysis", "continueToDone": True},
        created_at=now,
        updated_at=now,
    )


class FakeQueue:
    def __init__(self, reserved: ReservedOperation | None) -> None:
        self.reserved = reserved
        self.acknowledged: list[str] = []
        self.retried: list[str] = []
        self.recovered = 0

    def reserve(self, timeout: int = 5) -> ReservedOperation | None:
        value = self.reserved
        self.reserved = None
        return value

    def acknowledge(self, raw_payload: str) -> None:
        self.acknowledged.append(raw_payload)

    def retry(self, raw_payload: str) -> None:
        self.retried.append(raw_payload)

    def recover_reserved(self) -> int:
        return self.recovered


class FakeService:
    def __init__(self, initial: ProcessingJob | None, final: ProcessingJob | None) -> None:
        self.initial = initial
        self.final = final
        self.calls: list[tuple[int, str, dict]] = []
        self.raise_error = False

    def get_job(self, job_id: int) -> ProcessingJob | None:
        if self.calls:
            return self.final
        return self.initial

    def run_job(self, job_id: int, job_type: str, payload: dict) -> None:
        self.calls.append((job_id, job_type, payload))
        if self.raise_error:
            raise RuntimeError("database unavailable")


class OperationJobWorkerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.reserved = ReservedOperation(
            raw_payload='{"jobId":12}',
            job_id=12,
            job_type="video_process",
            payload={"videoId": 7, "stage": "analysis", "continueToDone": True},
        )

    def test_executes_and_acknowledges_queued_job(self) -> None:
        queue = FakeQueue(self.reserved)
        service = FakeService(make_job(JobStatus.queued), make_job(JobStatus.succeeded))
        worker = OperationJobWorker(queue=queue, service=service)

        result = worker.process_one(timeout=1)

        self.assertTrue(result.handled)
        self.assertTrue(result.completed)
        self.assertFalse(result.skipped)
        self.assertEqual(service.calls[0][0:2], (12, "video_process"))
        self.assertEqual(queue.acknowledged, [self.reserved.raw_payload])
        self.assertEqual(queue.retried, [])

    def test_acknowledges_terminal_duplicate_without_execution(self) -> None:
        queue = FakeQueue(self.reserved)
        service = FakeService(make_job(JobStatus.succeeded), None)
        worker = OperationJobWorker(queue=queue, service=service)

        result = worker.process_one(timeout=1)

        self.assertTrue(result.skipped)
        self.assertEqual(service.calls, [])
        self.assertEqual(queue.acknowledged, [self.reserved.raw_payload])

    def test_returns_message_to_ready_queue_on_unexpected_failure(self) -> None:
        queue = FakeQueue(self.reserved)
        service = FakeService(make_job(JobStatus.queued), None)
        service.raise_error = True
        worker = OperationJobWorker(queue=queue, service=service)

        with self.assertRaisesRegex(RuntimeError, "database unavailable"):
            worker.process_one(timeout=1)

        self.assertEqual(queue.acknowledged, [])
        self.assertEqual(queue.retried, [self.reserved.raw_payload])

    def test_returns_message_when_job_does_not_reach_terminal_status(self) -> None:
        queue = FakeQueue(self.reserved)
        service = FakeService(make_job(JobStatus.queued), make_job(JobStatus.running))
        worker = OperationJobWorker(queue=queue, service=service)

        with self.assertRaisesRegex(RuntimeError, "did not reach a terminal status"):
            worker.process_one(timeout=1)

        self.assertEqual(queue.acknowledged, [])
        self.assertEqual(queue.retried, [self.reserved.raw_payload])

    def test_delegates_startup_recovery(self) -> None:
        queue = FakeQueue(None)
        queue.recovered = 3
        worker = OperationJobWorker(queue=queue, service=FakeService(None, None))

        self.assertEqual(worker.recover_reserved(), 3)


if __name__ == "__main__":
    unittest.main()
