"""Operation service that persists honest stage-level progress for API jobs."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import json
from typing import Any

from echolens.analysis_worker import AnalysisWorker
from echolens.api.models import VideoProcessStage
from echolens.api.operations import OperationService, _operation_lock
from echolens.storage.management_repository import ManagementRepository
from echolens.storage.mysql import mysql_connection
from echolens.transcription_worker import TranscriptionWorker
from echolens.worker import AudioWorker


ProgressWriter = Callable[[dict[str, Any]], None]


class ProgressOperationService(OperationService):
    """Execute frontend jobs and persist completed-stage progress in result_json."""

    def run_job(self, job_id: int, job_type: str, payload: dict[str, Any]) -> None:
        """Execute one job while exposing its current stage to polling clients."""

        with _operation_lock:
            self._mark_running(job_id)
            try:
                if job_type == "scan":
                    partial = {
                        "progress": self._progress(
                            unit="stage",
                            completed=0,
                            total=1,
                            current_stage="scan",
                        )
                    }
                    self._mark_progress(job_id, partial)
                    result = self._run_scan(enqueue=bool(payload.get("enqueue", True)))
                    result["progress"] = self._progress(unit="stage", completed=1, total=1)
                elif job_type == "pipeline":
                    result = self._run_pipeline_with_progress(
                        job_id=job_id,
                        scan=bool(payload.get("scan", True)),
                        max_tasks=self._optional_int(payload.get("maxTasks")),
                    )
                elif job_type == "video_process":
                    result = self._execute_video_process(
                        video_db_id=int(payload["videoId"]),
                        stage=VideoProcessStage(str(payload.get("stage", "current"))),
                        continue_to_done=bool(payload.get("continueToDone", True)),
                        progress_writer=lambda partial: self._mark_progress(job_id, partial),
                    )
                elif job_type == "video_batch":
                    result = self._run_video_batch_with_progress(
                        job_id=job_id,
                        video_ids=[int(value) for value in payload.get("videoIds", [])],
                        stage=VideoProcessStage(str(payload.get("stage", "current"))),
                        continue_to_done=bool(payload.get("continueToDone", True)),
                    )
                else:
                    raise ValueError(f"Unsupported job type: {job_type}")
                self._mark_succeeded(job_id, result)
            except Exception as exc:
                self._mark_failed(job_id, str(exc))

    def _run_pipeline_with_progress(
        self,
        *,
        job_id: int,
        scan: bool,
        max_tasks: int | None,
    ) -> dict[str, Any]:
        stages: list[tuple[str, Callable[[], dict[str, Any]]]] = []
        if scan:
            stages.append(("scan", lambda: self._run_scan(enqueue=True)))
        stages.extend(
            [
                ("audio", lambda: self._run_audio_stage(max_tasks)),
                ("transcription", lambda: self._run_transcription_stage(max_tasks)),
                ("analysis", lambda: self._run_analysis_stage(max_tasks)),
            ]
        )

        result: dict[str, Any] = {}
        total = len(stages)
        for completed, (stage_name, runner) in enumerate(stages):
            result["progress"] = self._progress(
                unit="stage",
                completed=completed,
                total=total,
                current_stage=stage_name,
            )
            self._mark_progress(job_id, result)
            result[stage_name] = runner()

        result["progress"] = self._progress(unit="stage", completed=total, total=total)
        return result

    def _run_video_process(
        self,
        *,
        video_db_id: int,
        stage: VideoProcessStage,
        continue_to_done: bool,
    ) -> dict[str, Any]:
        """Keep the base service contract for batch helpers and tests."""

        return self._execute_video_process(
            video_db_id=video_db_id,
            stage=stage,
            continue_to_done=continue_to_done,
        )

    def _execute_video_process(
        self,
        *,
        video_db_id: int,
        stage: VideoProcessStage,
        continue_to_done: bool,
        progress_writer: ProgressWriter | None = None,
    ) -> dict[str, Any]:
        with mysql_connection(self.settings) as connection:
            repository = ManagementRepository(connection)
            resolved_stage = repository.prepare_video(video_db_id, stage.value)
            connection.commit()

        result: dict[str, Any] = {
            "videoId": video_db_id,
            "requestedStage": stage.value,
            "resolvedStage": resolved_stage,
            "continueToDone": continue_to_done,
            "stages": {},
        }
        if resolved_stage == "done":
            result["finalStatus"] = "done"
            result["progress"] = self._progress(unit="stage", completed=0, total=0)
            return result

        stage_sequences = {
            "audio": ["audio", "transcription", "analysis"],
            "transcription": ["transcription", "analysis"],
            "analysis": ["analysis"],
        }
        sequence = stage_sequences.get(resolved_stage)
        if sequence is None:
            raise ValueError(f"Unsupported processing stage: {resolved_stage}")
        if not continue_to_done:
            sequence = sequence[:1]

        total = len(sequence)
        for completed, current_stage in enumerate(sequence):
            result["progress"] = self._progress(
                unit="stage",
                completed=completed,
                total=total,
                current_stage=current_stage,
                current_video_id=video_db_id,
            )
            if progress_writer is not None:
                progress_writer(result)

            if current_stage == "audio":
                audio = AudioWorker(settings=self.settings).process_video(video_db_id, force=True)
                result["stages"]["audio"] = {
                    "completed": audio.completed,
                    "skipped": audio.skipped,
                }
                if not audio.completed:
                    raise RuntimeError("Audio extraction did not complete")
            elif current_stage == "transcription":
                transcription = TranscriptionWorker(settings=self.settings).process_video(video_db_id)
                result["stages"]["transcription"] = {
                    "completed": transcription.completed,
                    "failed": transcription.failed,
                    "error": transcription.error_message,
                }
                if not transcription.completed:
                    raise RuntimeError(
                        transcription.error_message or "Transcription did not complete"
                    )
            elif current_stage == "analysis":
                analysis = AnalysisWorker(settings=self.settings).process_video(video_db_id)
                result["stages"]["analysis"] = {
                    "completed": analysis.completed,
                    "failed": analysis.failed,
                    "error": analysis.error_message,
                }
                if not analysis.completed:
                    raise RuntimeError(analysis.error_message or "Analysis did not complete")

        result = self._with_final_status(result, video_db_id)
        result["progress"] = self._progress(unit="stage", completed=total, total=total)
        return result

    def _run_video_batch_with_progress(
        self,
        *,
        job_id: int,
        video_ids: list[int],
        stage: VideoProcessStage,
        continue_to_done: bool,
    ) -> dict[str, Any]:
        if not video_ids:
            raise ValueError("videoIds must contain at least one video")

        result: dict[str, Any] = {
            "requestedStage": stage.value,
            "continueToDone": continue_to_done,
            "total": len(video_ids),
            "completed": 0,
            "failed": 0,
            "items": [],
        }
        for index, video_id in enumerate(video_ids):
            result["progress"] = self._progress(
                unit="video",
                completed=index,
                total=len(video_ids),
                current_stage=stage.value,
                current_video_id=video_id,
            )
            self._mark_progress(job_id, result)
            try:
                video_result = self._execute_video_process(
                    video_db_id=video_id,
                    stage=stage,
                    continue_to_done=continue_to_done,
                )
                result["completed"] += 1
                result["items"].append(
                    {
                        "videoId": video_id,
                        "succeeded": True,
                        "resolvedStage": video_result.get("resolvedStage"),
                        "finalStatus": video_result.get("finalStatus"),
                        "stages": video_result.get("stages", {}),
                    }
                )
            except Exception as exc:
                result["failed"] += 1
                result["items"].append(
                    {
                        "videoId": video_id,
                        "succeeded": False,
                        "error": str(exc),
                    }
                )

        result["progress"] = self._progress(
            unit="video",
            completed=len(video_ids),
            total=len(video_ids),
        )
        return result

    def _mark_progress(self, job_id: int, result: dict[str, Any]) -> None:
        """Persist a partial result without changing the running job status."""

        now = datetime.now()
        with mysql_connection(self.settings) as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                UPDATE processing_jobs
                SET result_json = %s, updated_at = %s
                WHERE id = %s AND status = 'running'
                """,
                (json.dumps(result, ensure_ascii=False), now, job_id),
            )
            cursor.close()
            connection.commit()

    @staticmethod
    def _progress(
        *,
        unit: str,
        completed: int,
        total: int,
        current_stage: str | None = None,
        current_video_id: int | None = None,
    ) -> dict[str, Any]:
        percent = 100 if total <= 0 else min(100, int(completed * 100 / total))
        return {
            "unit": unit,
            "completed": completed,
            "total": total,
            "percent": percent,
            "currentStage": current_stage,
            "currentVideoId": current_video_id,
        }
