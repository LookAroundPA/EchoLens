"""Read-only HTTP routes consumed by the EchoLens frontend."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from echolens.api.dependencies import get_frontend_repository, get_frontend_service
from echolens.api.models import (
    CreatorDetailResponse,
    CreatorListResponse,
    DashboardResponse,
    SearchResponse,
    VideoDetail,
)
from echolens.api.service import FrontendService
from echolens.storage.frontend_repository import FrontendRepository


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
