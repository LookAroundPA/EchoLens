"""Tests for frontend-triggered background operation dispatch."""

import unittest

from echolens.api.models import VideoProcessStage
from echolens.api.operations import OperationService
from echolens.core.config import Settings


class FakeOperationService(OperationService):
    def __init__(self) -> None:
        super().__init__(Settings())
        self.events: list[tuple[str, object]] = []

    def _mark_running(self, job_id: int) -> None:
        self.events.append(("running", job_id))

    def _mark_succeeded(self, job_id: int, result: dict) -> None:
        self.events.append(("succeeded", result))

    def _mark_failed(self, job_id: int, error_message: str) -> None:
        self.events.append(("failed", error_message))

    def _run_scan(self, *, enqueue: bool) -> dict:
        return {"kind": "scan", "enqueue": enqueue}

    def _run_pipeline(self, *, scan: bool, max_tasks: int | None) -> dict:
        return {"kind": "pipeline", "scan": scan, "maxTasks": max_tasks}

    def _run_video_process(
        self,
        *,
        video_db_id: int,
        stage: VideoProcessStage,
        continue_to_done: bool,
    ) -> dict:
        return {
            "kind": "video",
            "videoId": video_db_id,
            "stage": stage.value,
            "continueToDone": continue_to_done,
        }


class FrontendOperationTests(unittest.TestCase):
    def test_dispatches_scan_pipeline_and_video_jobs(self) -> None:
        service = FakeOperationService()

        service.run_job(1, "scan", {"enqueue": False})
        service.run_job(2, "pipeline", {"scan": True, "maxTasks": 3})
        service.run_job(
            3,
            "video_process",
            {"videoId": 7, "stage": "analysis", "continueToDone": True},
        )

        succeeded = [event[1] for event in service.events if event[0] == "succeeded"]
        self.assertEqual(succeeded[0], {"kind": "scan", "enqueue": False})
        self.assertEqual(succeeded[1]["maxTasks"], 3)
        self.assertEqual(succeeded[2]["stage"], "analysis")
        self.assertEqual(succeeded[2]["videoId"], 7)

    def test_unknown_job_is_recorded_as_failed(self) -> None:
        service = FakeOperationService()
        service.run_job(8, "unknown", {})

        self.assertEqual(service.events[0], ("running", 8))
        self.assertEqual(service.events[1][0], "failed")
        self.assertIn("Unsupported job type", str(service.events[1][1]))


if __name__ == "__main__":
    unittest.main()
