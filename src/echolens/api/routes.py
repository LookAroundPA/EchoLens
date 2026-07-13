"""HTTP routes consumed by the EchoLens frontend."""

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse

from echolens.api.dependencies import (
    get_frontend_repository,
    get_frontend_service,
    get_management_repository,
    get_management_service,
    get_operation_service,
)
from echolens.api.management_service import ManagementService
from echolens.api.models import (
    CreatorDetailResponse,
    CreatorListResponse,
    DashboardResponse,
    JobListResponse,
    JobStatus,
    PipelineActionRequest,
    ProcessingJob,
    ScanActionRequest,
    SearchResponse,
    TagListResponse,
    VideoDetail,
    VideoListResponse,
    VideoProcessRequest,
)
from echolens.api.operations import OperationService
from echolens.api.service import FrontendService
from echolens.storage.frontend_repository import FrontendRepository
from echolens.storage.management_repository import ManagementRepository


router = APIRouter()


@router.get("/dashboard", response_model=DashboardResponse)
def dashboard(
    service: FrontendService = Depends(get_frontend_service),
) -> DashboardResponse:
    """Return overview counts, statuses, tags, and recently updated videos."""

    return service.dashboard()


@router.get("/creators", response_model=CreatorListResponse)
def creators(
    q: str | None = Query(default=None, min_length=1, max_length=255),
    limit: int = Query(default=100, ge=1, le=500),
    service: FrontendService = Depends(get_frontend_service),
) -> CreatorListResponse:
    """List creators with completed-content counts and frequent tags."""

    return service.creators(query=q, limit=limit)


@router.get("/creators/{sec_uid}", response_model=CreatorDetailResponse)
def creator_detail(
    sec_uid: str,
    limit: int = Query(default=100, ge=1, le=500),
    service: FrontendService = Depends(get_frontend_service),
) -> CreatorDetailResponse:
    """Return one creator and that creator's video timeline."""

    result = service.creator_detail(sec_uid, limit=limit)
    if result is None:
        raise HTTPException(status_code=404, detail="Creator not found")
    return result


@router.get("/videos", response_model=VideoListResponse)
def videos(
    q: str | None = Query(default=None, min_length=1, max_length=500),
    creator: str | None = Query(default=None, max_length=255),
    video_status: str | None = Query(default=None, alias="status", max_length=32),
    tag: str | None = Query(default=None, max_length=128),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: ManagementService = Depends(get_management_service),
) -> VideoListResponse:
    """List videos across all processing states with optional filters."""

    return service.videos(
        query=q,
        creator_sec_uid=creator,
        status=video_status,
        tag=tag,
        limit=limit,
        offset=offset,
    )


@router.get("/tags", response_model=TagListResponse)
def tags(
    creator: str | None = Query(default=None, max_length=255),
    limit: int = Query(default=100, ge=1, le=500),
    service: ManagementService = Depends(get_management_service),
) -> TagListResponse:
    """Return available analysis tags and their usage counts."""

    return service.tags(creator_sec_uid=creator, limit=limit)


@router.get("/videos/{video_db_id}", response_model=VideoDetail)
def video_detail(
    video_db_id: int,
    service: FrontendService = Depends(get_frontend_service),
) -> VideoDetail:
    """Return source metadata, analysis, transcript, and audio metadata for one video."""

    result = service.video_detail(video_db_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Video not found")
    return result


@router.get("/videos/{video_db_id}/audio", response_class=FileResponse)
def video_audio(
    video_db_id: int,
    repository: FrontendRepository = Depends(get_frontend_repository),
) -> FileResponse:
    """Stream an extracted WAV file to the browser."""

    raw_path = repository.get_audio_path(video_db_id)
    if raw_path is None:
        raise HTTPException(status_code=404, detail="Audio not found")
    audio_path = Path(raw_path)
    if not audio_path.is_file():
        raise HTTPException(status_code=404, detail="Audio file is missing")
    return FileResponse(
        path=audio_path,
        media_type="audio/wav",
        filename=f"echolens-{video_db_id}.wav",
    )


@router.get("/search", response_model=SearchResponse)
def search(
    q: str = Query(..., min_length=1, max_length=500),
    creator: str | None = Query(default=None, max_length=255),
    tag: str | None = Query(default=None, max_length=128),
    limit: int = Query(default=20, ge=1, le=200),
    service: FrontendService = Depends(get_frontend_service),
) -> SearchResponse:
    """Search descriptions, summaries, transcripts, tags, and key points."""

    return service.search(
        query=q,
        creator_sec_uid=creator,
        tag=tag,
        limit=limit,
    )


@router.get("/jobs", response_model=JobListResponse)
def jobs(
    job_status: JobStatus | None = Query(default=None, alias="status"),
    job_type: str | None = Query(default=None, max_length=64),
    video_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=500),
    service: OperationService = Depends(get_operation_service),
) -> JobListResponse:
    """List frontend-triggered processing jobs."""

    return service.list_jobs(
        status=job_status.value if job_status else None,
        job_type=job_type,
        video_id=video_id,
        limit=limit,
    )


@router.get("/jobs/{job_id}", response_model=ProcessingJob)
def job_detail(
    job_id: int,
    service: OperationService = Depends(get_operation_service),
) -> ProcessingJob:
    """Return the current state and result of one processing job."""

    job = service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post(
    "/actions/scan",
    response_model=ProcessingJob,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_scan(
    request: ScanActionRequest,
    background_tasks: BackgroundTasks,
    service: OperationService = Depends(get_operation_service),
) -> ProcessingJob:
    """Scan the source directory and optionally enqueue newly discovered videos."""

    payload = request.model_dump(by_alias=True, mode="json")
    job = service.create_job(job_type="scan", payload=payload)
    background_tasks.add_task(service.run_job, job.id, "scan", payload)
    return job


@router.post(
    "/actions/pipeline",
    response_model=ProcessingJob,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_pipeline(
    request: PipelineActionRequest,
    background_tasks: BackgroundTasks,
    service: OperationService = Depends(get_operation_service),
) -> ProcessingJob:
    """Run scan, audio extraction, transcription, and analysis in sequence."""

    payload = request.model_dump(by_alias=True, mode="json")
    job = service.create_job(job_type="pipeline", payload=payload)
    background_tasks.add_task(service.run_job, job.id, "pipeline", payload)
    return job


@router.post(
    "/videos/{video_db_id}/actions/process",
    response_model=ProcessingJob,
    status_code=status.HTTP_202_ACCEPTED,
)
def process_video(
    video_db_id: int,
    request: VideoProcessRequest,
    background_tasks: BackgroundTasks,
    repository: ManagementRepository = Depends(get_management_repository),
    service: OperationService = Depends(get_operation_service),
) -> ProcessingJob:
    """Continue or rerun one video from a selected stage."""

    if repository.get_video_state(video_db_id) is None:
        raise HTTPException(status_code=404, detail="Video not found")
    payload = {"videoId": video_db_id, **request.model_dump(by_alias=True, mode="json")}
    job = service.create_job(
        job_type="video_process",
        payload=payload,
        video_id=video_db_id,
    )
    background_tasks.add_task(service.run_job, job.id, "video_process", payload)
    return job
