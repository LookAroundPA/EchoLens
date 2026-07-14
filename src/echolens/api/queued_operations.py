"""API operation service that submits work to the independent Redis worker."""

from __future__ import annotations

from typing import Any

from echolens.api.models import ProcessingJob
from echolens.api.progress_operations import ProgressOperationService
from echolens.core.config import Settings
from echolens.storage.operation_queue import OperationQueue


class JobQueueUnavailable(RuntimeError):
    """Raised when a queued job cannot be handed to Redis."""


class QueuedOperationService(ProgressOperationService):
    """Create database jobs and enqueue them instead of running inside FastAPI."""

    def __init__(
        self,
        settings: Settings | None = None,
        queue: OperationQueue | None = None,
    ) -> None:
        super().__init__(settings=settings)
        self.queue = queue or OperationQueue(settings=self.settings)

    def create_job(
        self,
        *,
        job_type: str,
        payload: dict[str, Any],
        video_id: int | None = None,
    ) -> ProcessingJob:
        job = super().create_job(job_type=job_type, payload=payload, video_id=video_id)
        self.enqueue_job(job)
        return job

    def enqueue_job(self, job: ProcessingJob) -> None:
        try:
            self.queue.push(job_id=job.id, job_type=job.job_type, payload=job.payload)
        except Exception as exc:
            self._mark_failed(job.id, "Redis operation queue is unavailable")
            raise JobQueueUnavailable("Redis operation queue is unavailable") from exc
