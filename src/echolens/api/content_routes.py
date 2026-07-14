"""Manual content editing and portable video export endpoints."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import Field, field_validator

from echolens.api.content_service import ContentService
from echolens.api.dependencies import get_content_service
from echolens.api.models import ApiModel, VideoDetail


router = APIRouter(tags=["video content"])


class TranscriptUpdateRequest(ApiModel):
    transcript: str = Field(min_length=1, max_length=2_000_000)

    @field_validator("transcript")
    @classmethod
    def normalize_transcript(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Transcript cannot be empty")
        return normalized


class AnalysisUpdateRequest(ApiModel):
    summary: str = Field(default="", max_length=50_000)
    tags: list[str] = Field(default_factory=list, max_length=50)
    key_points: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("summary")
    @classmethod
    def normalize_summary(cls, value: str) -> str:
        return value.strip()

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = value.strip()
            if not normalized or normalized in seen:
                continue
            if len(normalized) > 128:
                raise ValueError("Each tag must be at most 128 characters")
            seen.add(normalized)
            result.append(normalized)
        return result

    @field_validator("key_points")
    @classmethod
    def normalize_key_points(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = value.strip()
            if not normalized or normalized in seen:
                continue
            if len(normalized) > 2_000:
                raise ValueError("Each key point must be at most 2000 characters")
            seen.add(normalized)
            result.append(normalized)
        return result


@router.patch("/videos/{video_db_id}/transcript", response_model=VideoDetail)
def update_transcript(
    video_db_id: int,
    request: TranscriptUpdateRequest,
    service: ContentService = Depends(get_content_service),
) -> VideoDetail:
    """Save corrected transcript text and mark existing analysis as stale."""

    try:
        result = service.update_transcript(video_db_id, request.transcript)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Video not found") from error
    if result is None:
        raise HTTPException(status_code=404, detail="Video not found")
    return result


@router.patch("/videos/{video_db_id}/analysis", response_model=VideoDetail)
def update_analysis(
    video_db_id: int,
    request: AnalysisUpdateRequest,
    service: ContentService = Depends(get_content_service),
) -> VideoDetail:
    """Save a small manually edited analysis for one video."""

    try:
        result = service.update_analysis(
            video_db_id,
            summary=request.summary,
            tags=request.tags,
            key_points=request.key_points,
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Video not found") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if result is None:
        raise HTTPException(status_code=404, detail="Video not found")
    return result


@router.get("/videos/{video_db_id}/export/markdown")
def export_video_markdown(
    video_db_id: int,
    service: ContentService = Depends(get_content_service),
) -> Response:
    """Download one video's current knowledge content as Markdown."""

    video = service.video_detail(video_db_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    return Response(
        content=service.export_markdown(video),
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="echolens-video-{video_db_id}.md"'
        },
    )


@router.get("/videos/{video_db_id}/export/json")
def export_video_json(
    video_db_id: int,
    service: ContentService = Depends(get_content_service),
) -> Response:
    """Download one video's current knowledge content as formatted JSON."""

    video = service.video_detail(video_db_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    return Response(
        content=json.dumps(service.export_json(video), ensure_ascii=False, indent=2),
        media_type="application/json; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="echolens-video-{video_db_id}.json"'
        },
    )
