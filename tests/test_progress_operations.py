"""Tests for progress-aware frontend operation execution."""

from copy import deepcopy
import unittest

from echolens.api.models import VideoProcessStage
from echolens.api.progress_operations import ProgressOperationService
from echolens.core.config import Settings


class FakeProgressOperationService(ProgressOperationService):
    def __init__(self) -> None:
        super().__init__(Settings())
        self.events: list[tuple[str, object]] = []

    def _mark_running(self, job_id: int) -> None:
        self.events.append(("running", job_id))

    def _mark_progress(self, job_id: int, result: dict) -> None:
        self.events.append(("progress", deepcopy(result)))

    def _mark_succeeded(self, job_id: int, result: dict) -> None:
        self.events.append(("succeeded", deepcopy(result)))

    def _mark_failed(self, job_id: int, error_message: str) -> None:
        self.events.append(("failed", error_message))

    def _run_scan(self, *, enqueue: bool) -> dict:
        return {"discovered": 2, "enqueue": enqueue}

    def _run_audio_stage(self, limit: int | None) -> dict:
        return {"processed": limit or 2, "completed": limit or 2, "skipped": 0}

    def _run_transcription_stage(self, limit: int | None) -> dict:
        return {"processed": limit or 2, "completed": limit or 2, "failed": 0}

    def _run_analysis_stage(self, limit: int | None) -> dict:
        return {"processed": limit or 2, "completed": limit or 2, "failed": 0}

    def _run_semantic_index(self, *, rebuild: bool) -> dict:
        return {"discovered": 2, "indexed": 2, "skipped": 0, "removed": 0, "chunks": 4, "rebuilt": rebuild}

    def _execute_video_process(
        self,
        *,
        video_db_id: int,
        stage: VideoProcessStage,
        continue_to_done: bool,
        progress_writer=None,
    ) -> dict:
        if video_db_id == 2:
            raise RuntimeError("analysis unavailable")
        return {
            "videoId": video_db_id,
            "resolvedStage": stage.value,
            "continueToDone": continue_to_done,
            "finalStatus": "done",
            "stages": {stage.value: {"completed": True}},
        }


class ProgressOperationTests(unittest.TestCase):
    def test_pipeline_reports_each_real_stage(self) -> None:
        service = FakeProgressOperationService()

        service.run_job(1, "pipeline", {"scan": True, "maxTasks": 3})

        progress = [event[1]["progress"] for event in service.events if event[0] == "progress"]
        self.assertEqual(
            [item["currentStage"] for item in progress],
            ["scan", "audio", "transcription", "analysis", "semantic_index"],
        )
        succeeded = next(event[1] for event in service.events if event[0] == "succeeded")
        self.assertEqual(succeeded["progress"]["percent"], 100)
        self.assertEqual(succeeded["progress"]["completed"], 5)

    def test_batch_reports_current_video_and_keeps_partial_failures(self) -> None:
        service = FakeProgressOperationService()

        service.run_job(
            2,
            "video_batch",
            {
                "videoIds": [1, 2, 3],
                "stage": "analysis",
                "continueToDone": True,
            },
        )

        progress = [event[1]["progress"] for event in service.events if event[0] == "progress"]
        self.assertEqual([item["currentVideoId"] for item in progress], [1, 2, 3])
        succeeded = next(event[1] for event in service.events if event[0] == "succeeded")
        self.assertEqual(succeeded["completed"], 2)
        self.assertEqual(succeeded["failed"], 1)
        self.assertEqual(succeeded["progress"]["percent"], 100)

    def test_empty_batch_is_failed_without_fake_progress(self) -> None:
        service = FakeProgressOperationService()
        service.run_job(3, "video_batch", {"videoIds": []})

        self.assertEqual(service.events[0], ("running", 3))
        self.assertEqual(service.events[1][0], "failed")
        self.assertNotIn("progress", [event[0] for event in service.events])


if __name__ == "__main__":
    unittest.main()
