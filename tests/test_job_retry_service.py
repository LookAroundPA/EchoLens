"""Unit tests for failed job retry persistence."""

from datetime import datetime
import unittest
from unittest.mock import patch

from echolens.api.job_retry import JobRetryConflict, JobRetryService
from echolens.core.config import Settings


class FakeCursor:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = list(rows)
        self.executed: list[tuple[str, tuple | None]] = []
        self.lastrowid = 17

    def execute(self, statement: str, params: tuple | None = None) -> None:
        self.executed.append((statement, params))

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def close(self) -> None:
        return None


class FakeConnection:
    def __init__(self, rows: list[dict]) -> None:
        self.cursor_instance = FakeCursor(rows)
        self.committed = False

    def cursor(self, dictionary: bool = False) -> FakeCursor:
        self.dictionary = dictionary
        return self.cursor_instance

    def commit(self) -> None:
        self.committed = True


class FakeConnectionContext:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    def __enter__(self) -> FakeConnection:
        return self.connection

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None


def job_row(*, job_id: int, status: str, retry_count: int) -> dict:
    now = datetime(2026, 7, 14, 12, 0, 0)
    return {
        "id": job_id,
        "video_id": None,
        "job_type": "pipeline",
        "status": status,
        "retry_count": retry_count,
        "payload_json": '{"scan": false, "maxTasks": 3}',
        "result_json": None,
        "error_message": "failure" if status == "failed" else None,
        "created_at": now,
        "updated_at": now,
        "started_at": now,
        "finished_at": now,
    }


class JobRetryServiceTests(unittest.TestCase):
    def test_failed_job_is_cloned_with_incremented_retry_count(self) -> None:
        connection = FakeConnection([
            job_row(job_id=5, status="failed", retry_count=1),
            job_row(job_id=17, status="queued", retry_count=2),
        ])
        service = JobRetryService(Settings())

        with patch(
            "echolens.api.job_retry.mysql_connection",
            return_value=FakeConnectionContext(connection),
        ):
            result = service.retry(5)

        self.assertIsNotNone(result)
        self.assertEqual(result.id, 17)
        self.assertEqual(result.retry_count, 2)
        self.assertEqual(result.payload, {"scan": False, "maxTasks": 3})
        self.assertTrue(connection.committed)

        insert = next(
            item for item in connection.cursor_instance.executed
            if "INSERT INTO processing_jobs" in item[0]
        )
        self.assertEqual(insert[1][2], 2)

    def test_running_job_is_not_retryable(self) -> None:
        connection = FakeConnection([job_row(job_id=9, status="running", retry_count=0)])
        service = JobRetryService(Settings())

        with patch(
            "echolens.api.job_retry.mysql_connection",
            return_value=FakeConnectionContext(connection),
        ):
            with self.assertRaises(JobRetryConflict):
                service.retry(9)

        self.assertFalse(connection.committed)


if __name__ == "__main__":
    unittest.main()
