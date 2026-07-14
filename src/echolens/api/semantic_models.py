"""HTTP contracts for local semantic search and grounded question answering."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from echolens.api.models import ApiModel, VideoSummary


class SemanticIndexStatusResponse(ApiModel):
    ready: bool
    model: str | None = None
    video_count: int = 0
    chunk_count: int = 0
    indexed_at: datetime | None = None
    auto_sync: bool = True


class SemanticSyncRequest(ApiModel):
    rebuild: bool = False


class SemanticMatch(ApiModel):
    source_type: str
    text: str
    start: float | None = None
    end: float | None = None
    segment_index: int | None = None
    segment_count: int = 0
    score: float
    semantic_score: float
    keyword_score: float


class SemanticSearchHit(VideoSummary):
    match: SemanticMatch


class SemanticSearchResponse(ApiModel):
    items: list[SemanticSearchHit] = Field(default_factory=list)
    total: int = 0
    index: SemanticIndexStatusResponse


class AskRequest(ApiModel):
    question: str = Field(min_length=2, max_length=2000)
    creator_sec_uid: str | None = Field(default=None, max_length=255)
    tag: str | None = Field(default=None, max_length=128)
    max_sources: int | None = Field(default=None, ge=2, le=20)
    thinking: bool = False


class KnowledgeSource(ApiModel):
    source_id: str
    video_id: int
    platform_video_id: str
    creator_sec_uid: str
    creator_name: str | None = None
    title: str
    published_at: datetime | None = None
    source_type: str
    start: float | None = None
    end: float | None = None
    segment_index: int | None = None
    segment_count: int = 0
    text: str
    score: float


class AskResponse(ApiModel):
    answer: str
    insufficient_evidence: bool
    sources: list[KnowledgeSource] = Field(default_factory=list)
    model: str | None = None
    thinking: bool = False
