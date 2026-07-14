"""HTTP routes for local semantic search and grounded cross-video questions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from echolens.api.dependencies import get_knowledge_service, get_operation_service
from echolens.api.knowledge_service import KnowledgeService
from echolens.api.models import ProcessingJob
from echolens.api.queued_operations import QueuedOperationService
from echolens.api.semantic_models import (
    AskRequest,
    AskResponse,
    SemanticIndexStatusResponse,
    SemanticSearchResponse,
    SemanticSyncRequest,
)


router = APIRouter()


@router.get("/semantic/status", response_model=SemanticIndexStatusResponse)
def semantic_status(
    service: KnowledgeService = Depends(get_knowledge_service),
) -> SemanticIndexStatusResponse:
    """Return local index readiness, size, model, and latest sync time."""

    return service.status()


@router.get("/semantic/search", response_model=SemanticSearchResponse)
def semantic_search(
    q: str = Query(..., min_length=1, max_length=500),
    creator: str | None = Query(default=None, max_length=255),
    tag: str | None = Query(default=None, max_length=128),
    limit: int = Query(default=20, ge=1, le=100),
    service: KnowledgeService = Depends(get_knowledge_service),
) -> SemanticSearchResponse:
    """Run local dense and keyword hybrid retrieval over timestamped content."""

    return service.search(
        q,
        creator_sec_uid=creator,
        tag=tag,
        limit=limit,
    )


@router.post(
    "/semantic/actions/sync",
    response_model=ProcessingJob,
    status_code=status.HTTP_202_ACCEPTED,
)
def sync_semantic_index(
    request: SemanticSyncRequest,
    service: QueuedOperationService = Depends(get_operation_service),
) -> ProcessingJob:
    """Queue an incremental semantic sync or a complete local index rebuild."""

    return service.create_job(
        job_type="semantic_index",
        payload=request.model_dump(by_alias=True, mode="json"),
    )


@router.post("/ask", response_model=AskResponse)
def ask_knowledge(
    request: AskRequest,
    service: KnowledgeService = Depends(get_knowledge_service),
) -> AskResponse:
    """Answer one question using only retrieved local video evidence."""

    try:
        return service.ask(
            request.question,
            creator_sec_uid=request.creator_sec_uid,
            tag=request.tag,
            max_sources=request.max_sources,
            thinking=request.thinking,
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
