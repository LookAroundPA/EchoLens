"""Independent worker for frontend-triggered EchoLens operations."""

from __future__ import annotations

from dataclasses import dataclass

from echolens.api.models import JobStatus
from echolens.api.progress_operations import ProgressOperationService
from echolens.core.config import Settings, get_settings
from echolens.storage.operation_queue import OperationQueue


@dataclass(frozen=True)
class OperationWorkerResult:
    handled: bool
    completed: bool
    skipped: bool
    job_id: int | None = None


class OperationJobWorker:
    """Serially execute jobs reserved from the Redis operation queue."""

    def __init__(
        self,
        settings: Settings | None = None,
        queue: OperationQueue | None = None,
        service: ProgressOperationService | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.queue = queue or OperationQueue(settings=self.settings)
        self.service = service or ProgressOperationService(settings=self.settings)

    def recover_reserved(self) -> int:
        """Recover messages reserved by a previously stopped single worker."""

        return self.queue.recover_reserved()

    def process_one(self, timeout: int = 5) -> OperationWorkerResult:
        reserved = self.queue.reserve(timeout=timeout)
        if reserved is None:
            return OperationWorkerResult(handled=False, completed=False, skipped=False)

        try:
            job = self.service.get_job(reserved.job_id)
            if job is None:
                self.queue.acknowledge(reserved.raw_payload)
                return OperationWorkerResult(
                    handled=True,
                    completed=False,
                    skipped=True,
                    job_id=reserved.job_id,
                )
            if job.status in {JobStatus.succeeded, JobStatus.failed}:
                self.queue.acknowledge(reserved.raw_payload)
                return OperationWorkerResult(
                    handled=True,
                    completed=False,
                    skipped=True,
                    job_id=reserved.job_id,
                )

            self.service.run_job(
                reserved.job_id,
                reserved.job_type,
                reserved.payload,
            )
            final_job = self.service.get_job(reserved.job_id)
            completed = final_job is not None and final_job.status == JobStatus.succeeded
            self.queue.acknowledge(reserved.raw_payload)
            return OperationWorkerResult(
                handled=True,
                completed=completed,
                skipped=False,
                job_id=reserved.job_id,
            )
        except Exception:
            self.queue.retry(reserved.raw_payload)
            raise
