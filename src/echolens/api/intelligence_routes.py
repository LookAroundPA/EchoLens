"""HTTP routes for normalized topic intelligence and market radar."""

from fastapi import APIRouter, Depends, HTTPException, Query

from echolens.api.dependencies import get_intelligence_api_service
from echolens.api.intelligence_models import (
    TopicDetailResponse,
    TopicHistoryResponse,
    TopicRadarResponse,
    TopicStatusFilter,
    TopicTrendFilter,
    TopicType,
    TopicWindowDays,
)
from echolens.api.intelligence_service import IntelligenceApiService


router = APIRouter(prefix="/intelligence", tags=["intelligence"])


@router.get("/topics", response_model=TopicRadarResponse)
def topic_radar(
    window_days: TopicWindowDays = Query(default=TopicWindowDays.seven, alias="windowDays"),
    topic_status: TopicStatusFilter = Query(default="all", alias="status"),
    topic_type: TopicType | None = Query(default=None, alias="type"),
    trend: TopicTrendFilter = Query(default="all"),
    limit: int = Query(default=50, ge=1, le=200),
    service: IntelligenceApiService = Depends(get_intelligence_api_service),
) -> TopicRadarResponse:
    """Rank topics by explainable 7-day or 30-day attention and stance metrics."""

    return service.radar(
        window_days=int(window_days),
        topic_status=topic_status,
        topic_type=topic_type,
        trend_filter=trend,
        limit=limit,
    )


@router.get("/topics/{topic_id}", response_model=TopicDetailResponse)
def topic_detail(
    topic_id: int,
    window_days: TopicWindowDays = Query(default=TopicWindowDays.thirty, alias="windowDays"),
    opinion_limit: int = Query(default=50, ge=1, le=200, alias="opinionLimit"),
    service: IntelligenceApiService = Depends(get_intelligence_api_service),
) -> TopicDetailResponse:
    """Return topic aliases, current heat, latest opinions, and recent changes."""

    result = service.topic_detail(
        topic_id,
        window_days=int(window_days),
        opinion_limit=opinion_limit,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    return result


@router.get("/topics/{topic_id}/history", response_model=TopicHistoryResponse)
def topic_history(
    topic_id: int,
    creator: str | None = Query(default=None, min_length=1, max_length=255),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: IntelligenceApiService = Depends(get_intelligence_api_service),
) -> TopicHistoryResponse:
    """Return a traceable topic opinion timeline, optionally for one creator."""

    result = service.topic_history(
        topic_id,
        creator_sec_uid=creator,
        limit=limit,
        offset=offset,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    return result
