"""Tests for serial processing of selected videos."""

import unittest

from echolens.api.models import VideoProcessStage
from echolens.api.operations import OperationService
from echolens.core.config import Settings


class FakeBatchOperationService(OperationService):
    def __init__(self) -> None:
        super().__init__(Settings())
        self.events: list[tuple[str, object]] = []

    def _mark_running(self, job_id: int) -> None:
        self.events.append(("running", job_id))

    def _mark_succeeded(self, job_id: int, result: dict) -> None:
        self.events.append(("succeeded", result))

    def _mark_failed(self, job_id: int, error_message: str) -> None:
        self.events.append(("failed", error_message))

    def _run_video_process(
        self,
        *,
        video_db_id: int,
        stage: VideoProcessStage,
        continue_to_done: bool,
    ) -> dict:
        if video_db_id == 2:
            raise RuntimeError("transcription unavailable")
        return {
            "videoId": video_db_id,
            "requestedStage": stage.value,
            "resolvedStage": stage.value,
            "continueToDone": continue_to_done,
            "finalStatus": "done",
            "stages": {stage.value: {"completed": True}},
        }


class BatchOperationTests(unittest.TestCase):
    def test_batch_continues_after_one_video_fails(self) -> None:
        service = FakeBatchOperationService()

        service.run_job(
            9,
            "video_batch",
            {
                "videoIds": [1, 2, 3],
                "stage": "transcription",
                "continueToDone": True,
            },
        )

        self.assertEqual(service.events[0], ("running", 9))
        self.assertEqual(service.events[1][0], "succeeded")
        result = service.events[1][1]
        self.assertEqual(result["total"], 3)
        self.assertEqual(result["completed"], 2)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["items"][1]["videoId"], 2)
        self.assertFalse(result["items"][1]["succeeded"])

    def test_empty_batch_is_recorded_as_failed(self) -> None:
        service = FakeBatchOperationService()
        service.run_job(10, "video_batch", {"videoIds": []})

        self.assertEqual(service.events[0], ("running", 10))
        self.assertEqual(service.events[1][0], "failed")
        self.assertIn("at least one video", str(service.events[1][1]))


if __name__ == "__main__":
    unittest.main()
