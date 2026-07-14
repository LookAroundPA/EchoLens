"""HTTP endpoint for processing multiple selected videos."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import Field, field_validator

from echolens.api.dependencies import get_management_repository, get_operation_service
from echolens.api.models import ApiModel, ProcessingJob, VideoProcessStage
from echolens.api.operations import OperationService
from echolens.storage.management_repository import ManagementRepository


router = APIRouter()


class BatchVideoProcessRequest(ApiModel):
    """Request one processing stage for a selected set of videos."""

    video_ids: list[int] = Field(min_length=1)
    stage: VideoProcessStage = VideoProcessStage.current
    continue_to_done: bool = True

    @field_validator("video_ids")
    @classmethod
    def validate_video_ids(cls, video_ids: list[int]) -> list[int]:
        if any(video_id < 1 for video_id in video_ids):
            raise ValueError("videoIds must contain positive integers")
        return list(dict.fromkeys(video_ids))


@router.post(
    "/videos/actions/batch-process",
    response_model=ProcessingJob,
    status_code=status.HTTP_202_ACCEPTED,
)
def process_videos(
    request: BatchVideoProcessRequest,
    background_tasks: BackgroundTasks,
    repository: ManagementRepository = Depends(get_management_repository),
    service: OperationService = Depends(get_operation_service),
) -> ProcessingJob:
    """Create one serial task for selected videos and preserve per-video results."""

    missing_ids = [
        video_id
        for video_id in request.video_ids
        if repository.get_video_state(video_id) is None
    ]
    if missing_ids:
        missing = ", ".join(str(video_id) for video_id in missing_ids)
        raise HTTPException(status_code=404, detail=f"Videos not found: {missing}")

    payload = request.model_dump(by_alias=True, mode="json")
    job = service.create_job(job_type="video_batch", payload=payload)
    background_tasks.add_task(service.run_job, job.id, "video_batch", payload)
    return job
