"""Tests for the database-driven DeepSeek analysis worker."""

from contextlib import contextmanager
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from echolens.analysis.models import AnalysisResult
import echolens.analysis_worker as worker_module


class FakeConnection:
    def commit(self) -> None:
        pass


@contextmanager
def fake_mysql_connection(settings: object):
    yield FakeConnection()


class FakeRepository:
    next_video: dict[str, object] | None = None
    saved: list[tuple[int, AnalysisResult, str]] = []
    failures: list[tuple[int, str]] = []

    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    def claim_next_video(self) -> dict[str, object] | None:
        value = type(self).next_video
        type(self).next_video = None
        return value

    def save_result(self, video_db_id: int, result: AnalysisResult, model_name: str) -> None:
        type(self).saved.append((video_db_id, result, model_name))

    def mark_failed(self, video_db_id: int, error_message: str) -> None:
        type(self).failures.append((video_db_id, error_message))


class FakeAnalyzer:
    def __init__(
        self,
        result: AnalysisResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error

    def analyze(self, transcript_text: str, description: str | None = None) -> AnalysisResult:
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


class AnalysisWorkerTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeRepository.saved = []
        FakeRepository.failures = []

    def test_completes_analysis(self) -> None:
        FakeRepository.next_video = {
            "id": 7,
            "transcript_text": "内容",
            "description": "描述",
        }
        result = AnalysisResult(summary="摘要", tags=["标签"], key_points=["观点"])
        settings = SimpleNamespace(llm_model="deepseek-v4-flash")
        worker = worker_module.AnalysisWorker(
            settings=settings,
            analyzer=FakeAnalyzer(result=result),
        )

        with patch.object(worker_module, "mysql_connection", fake_mysql_connection), patch.object(
            worker_module,
            "AnalysisRepository",
            FakeRepository,
        ):
            outcome = worker.process_one()

        self.assertTrue(outcome.completed)
        self.assertEqual(FakeRepository.saved[0][0], 7)
        self.assertEqual(FakeRepository.saved[0][2], "deepseek-v4-flash")

    def test_records_failure(self) -> None:
        FakeRepository.next_video = {
            "id": 8,
            "transcript_text": "内容",
            "description": None,
        }
        settings = SimpleNamespace(llm_model="deepseek-v4-flash")
        worker = worker_module.AnalysisWorker(
            settings=settings,
            analyzer=FakeAnalyzer(error=RuntimeError("API error")),
        )

        with patch.object(worker_module, "mysql_connection", fake_mysql_connection), patch.object(
            worker_module,
            "AnalysisRepository",
            FakeRepository,
        ):
            outcome = worker.process_one()

        self.assertTrue(outcome.failed)
        self.assertEqual(FakeRepository.failures, [(8, "API error")])


if __name__ == "__main__":
    unittest.main()
