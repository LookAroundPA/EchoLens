"""HTTP endpoint for retrying failed frontend processing jobs."""

from fastapi import APIRouter, Depends, HTTPException, status

from echolens.api.dependencies import get_operation_service
from echolens.api.job_retry import JobRetryConflict, JobRetryService
from echolens.api.models import ProcessingJob
from echolens.api.queued_operations import QueuedOperationService


router = APIRouter()


def get_job_retry_service() -> JobRetryService:
    """Provide the retry service as an overridable FastAPI dependency."""

    return JobRetryService()


@router.post(
    "/jobs/{job_id}/actions/retry",
    response_model=ProcessingJob,
    status_code=status.HTTP_202_ACCEPTED,
)
def retry_job(
    job_id: int,
    retry_service: JobRetryService = Depends(get_job_retry_service),
    operation_service: QueuedOperationService = Depends(get_operation_service),
) -> ProcessingJob:
    """Create and enqueue a new task from one failed processing job."""

    try:
        job = retry_service.retry(job_id)
    except JobRetryConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    operation_service.enqueue_job(job)
    return job
