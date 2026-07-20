"""Minimal background operations exposed to the frontend API."""

from __future__ import annotations

from collections import Counter
from threading import Lock
from typing import Any

from echolens.analysis_worker import AnalysisWorker
from echolens.api.models import (
    JobListResponse,
    ProcessingJob,
    VideoProcessStage,
    processing_job_from_row,
)
from echolens.collector.local_ingest import LocalIngestService
from echolens.collector.local_scanner import LocalSourceScanner
from echolens.core.config import Settings, get_settings
from echolens.semantic.service import SemanticIndexService
from echolens.storage.management_repository import ManagementRepository
from echolens.storage.mysql import mysql_connection
from echolens.transcription_worker import TranscriptionWorker
from echolens.worker import AudioWorker


_operation_lock = Lock()


class OperationService:
    """Create, query, and execute user-triggered frontend operations."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def create_job(
        self,
        *,
        job_type: str,
        payload: dict[str, Any],
        video_id: int | None = None,
    ) -> ProcessingJob:
        with mysql_connection(self.settings) as connection:
            row = ManagementRepository(connection).create_job(
                job_type=job_type,
                payload=payload,
                video_id=video_id,
            )
            connection.commit()
        return processing_job_from_row(row)

    def get_job(self, job_id: int) -> ProcessingJob | None:
        with mysql_connection(self.settings) as connection:
            row = ManagementRepository(connection).get_job(job_id)
        return processing_job_from_row(row) if row is not None else None

    def list_jobs(
        self,
        *,
        status: str | None,
        job_type: str | None,
        video_id: int | None,
        limit: int,
    ) -> JobListResponse:
        with mysql_connection(self.settings) as connection:
            rows, total = ManagementRepository(connection).list_jobs(
                status=status,
                job_type=job_type,
                video_id=video_id,
                limit=limit,
            )
        return JobListResponse(
            items=[processing_job_from_row(row) for row in rows],
            total=total,
        )

    def run_job(self, job_id: int, job_type: str, payload: dict[str, Any]) -> None:
        """Execute one submitted operation and persist its final result."""

        with _operation_lock:
            self._mark_running(job_id)
            try:
                if job_type == "scan":
                    result = self._run_scan(enqueue=bool(payload.get("enqueue", True)))
                elif job_type == "pipeline":
                    result = self._run_pipeline(
                        scan=bool(payload.get("scan", True)),
                        max_tasks=self._optional_int(payload.get("maxTasks")),
                    )
                elif job_type == "video_process":
                    result = self._run_video_process(
                        video_db_id=int(payload["videoId"]),
                        stage=VideoProcessStage(str(payload.get("stage", "current"))),
                        continue_to_done=bool(payload.get("continueToDone", True)),
                    )
                elif job_type == "video_batch":
                    result = self._run_video_batch(
                        video_ids=[int(value) for value in payload.get("videoIds", [])],
                        stage=VideoProcessStage(str(payload.get("stage", "current"))),
                        continue_to_done=bool(payload.get("continueToDone", True)),
                    )
                elif job_type == "semantic_index":
                    result = self._run_semantic_index(
                        rebuild=bool(payload.get("rebuild", False))
                    )
                else:
                    raise ValueError(f"Unsupported job type: {job_type}")
                self._mark_succeeded(job_id, result)
            except Exception as exc:
                self._mark_failed(job_id, str(exc))

    def _run_scan(self, *, enqueue: bool) -> dict[str, Any]:
        scanner = LocalSourceScanner(self.settings)
        items = scanner.scan()
        issue_codes = Counter(issue.code for issue in scanner.issues)
        result: dict[str, Any] = {
            "discovered": len(items),
            "skipped": len(scanner.issues),
            "issueCounts": dict(issue_codes),
            "enqueue": enqueue,
        }
        if enqueue:
            ingest = LocalIngestService().ingest(items)
            result.update(
                {
                    "inserted": ingest.inserted,
                    "queued": ingest.queued,
                    "skippedExisting": ingest.skipped_existing,
                }
            )
        return result

    def _run_pipeline(self, *, scan: bool, max_tasks: int | None) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if scan:
            result["scan"] = self._run_scan(enqueue=True)
        result["audio"] = self._run_audio_stage(max_tasks)
        result["transcription"] = self._run_transcription_stage(max_tasks)
        result["analysis"] = self._run_analysis_stage(max_tasks)
        result["semantic_index"] = self._run_semantic_index(rebuild=False)
        return result

    def _run_video_process(
        self,
        *,
        video_db_id: int,
        stage: VideoProcessStage,
        continue_to_done: bool,
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
            return result

        if resolved_stage == "audio":
            audio = AudioWorker(settings=self.settings).process_video(video_db_id, force=True)
            result["stages"]["audio"] = {
                "completed": audio.completed,
                "skipped": audio.skipped,
            }
            if not audio.completed:
                raise RuntimeError("Audio extraction did not complete")
            if not continue_to_done:
                return self._with_final_status(result, video_db_id)
            resolved_stage = "transcription"

        if resolved_stage == "transcription":
            transcription = TranscriptionWorker(settings=self.settings).process_video(video_db_id)
            result["stages"]["transcription"] = {
                "completed": transcription.completed,
                "failed": transcription.failed,
                "error": transcription.error_message,
            }
            if not transcription.completed:
                raise RuntimeError(transcription.error_message or "Transcription did not complete")
            if not continue_to_done:
                return self._with_final_status(result, video_db_id)
            resolved_stage = "analysis"

        if resolved_stage == "analysis":
            analysis = AnalysisWorker(settings=self.settings).process_video(video_db_id)
            result["stages"]["analysis"] = {
                "completed": analysis.completed,
                "failed": analysis.failed,
                "error": analysis.error_message,
            }
            if not analysis.completed:
                raise RuntimeError(analysis.error_message or "Analysis did not complete")

        return self._with_final_status(result, video_db_id)

    def _run_video_batch(
        self,
        *,
        video_ids: list[int],
        stage: VideoProcessStage,
        continue_to_done: bool,
    ) -> dict[str, Any]:
        """Process every selected video while preserving each individual outcome."""

        if not video_ids:
            raise ValueError("videoIds must contain at least one video")

        completed = failed = 0
        items: list[dict[str, Any]] = []
        for video_id in video_ids:
            try:
                video_result = self._run_video_process(
                    video_db_id=video_id,
                    stage=stage,
                    continue_to_done=continue_to_done,
                )
                completed += 1
                items.append(
                    {
                        "videoId": video_id,
                        "succeeded": True,
                        "resolvedStage": video_result.get("resolvedStage"),
                        "finalStatus": video_result.get("finalStatus"),
                        "stages": video_result.get("stages", {}),
                    }
                )
            except Exception as exc:
                failed += 1
                items.append(
                    {
                        "videoId": video_id,
                        "succeeded": False,
                        "error": str(exc),
                    }
                )

        return {
            "requestedStage": stage.value,
            "continueToDone": continue_to_done,
            "total": len(video_ids),
            "completed": completed,
            "failed": failed,
            "items": items,
        }

    def _run_semantic_index(self, *, rebuild: bool) -> dict[str, Any]:
        return SemanticIndexService(self.settings).sync(rebuild=rebuild).as_dict()

    def _run_audio_stage(self, limit: int | None) -> dict[str, int]:
        processed = completed = skipped = 0
        worker = AudioWorker(settings=self.settings)
        while limit is None or processed < limit:
            item = worker.process_one(timeout=1)
            if not item.handled:
                break
            processed += 1
            completed += int(item.completed)
            skipped += int(item.skipped)
        return {"processed": processed, "completed": completed, "skipped": skipped}

    def _run_transcription_stage(self, limit: int | None) -> dict[str, int]:
        processed = completed = failed = 0
        worker = TranscriptionWorker(settings=self.settings)
        while limit is None or processed < limit:
            item = worker.process_one()
            if not item.handled:
                break
            processed += 1
            completed += int(item.completed)
            failed += int(item.failed)
        return {"processed": processed, "completed": completed, "failed": failed}

    def _run_analysis_stage(self, limit: int | None) -> dict[str, int]:
        processed = completed = failed = 0
        worker = AnalysisWorker(settings=self.settings)
        while limit is None or processed < limit:
            item = worker.process_one()
            if not item.handled:
                break
            processed += 1
            completed += int(item.completed)
            failed += int(item.failed)
        return {"processed": processed, "completed": completed, "failed": failed}

    def _with_final_status(self, result: dict[str, Any], video_db_id: int) -> dict[str, Any]:
        with mysql_connection(self.settings) as connection:
            row = ManagementRepository(connection).get_video_state(video_db_id)
        result["finalStatus"] = str(row["status"]) if row is not None else None
        return result

    def _mark_running(self, job_id: int) -> None:
        with mysql_connection(self.settings) as connection:
            ManagementRepository(connection).mark_job_running(job_id)
            connection.commit()

    def _mark_succeeded(self, job_id: int, result: dict[str, Any]) -> None:
        with mysql_connection(self.settings) as connection:
            ManagementRepository(connection).mark_job_succeeded(job_id, result)
            connection.commit()

    def _mark_failed(self, job_id: int, error_message: str) -> None:
        with mysql_connection(self.settings) as connection:
            ManagementRepository(connection).mark_job_failed(job_id, error_message)
            connection.commit()

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        return int(value) if value is not None else None
