"""Application service for semantic search and grounded cross-video questions."""

from __future__ import annotations

from datetime import datetime

from echolens.api.semantic_models import (
    AskResponse,
    KnowledgeSource,
    SemanticIndexStatusResponse,
    SemanticMatch,
    SemanticSearchHit,
    SemanticSearchResponse,
)
from echolens.core.config import Settings, get_settings
from echolens.semantic.qa import DeepSeekKnowledgeAnswerer
from echolens.semantic.service import SemanticIndexService, SemanticResult


class KnowledgeService:
    """Combine local retrieval with DeepSeek V4 Pro answer synthesis."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        index: SemanticIndexService | None = None,
        answerer: DeepSeekKnowledgeAnswerer | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.index = index or SemanticIndexService(self.settings)
        self.answerer = answerer or DeepSeekKnowledgeAnswerer(self.settings)

    def status(self) -> SemanticIndexStatusResponse:
        value = self.index.status()
        return SemanticIndexStatusResponse(
            ready=value.ready,
            model=value.model,
            video_count=value.video_count,
            chunk_count=value.chunk_count,
            indexed_at=value.indexed_at,
            auto_sync=self.settings.semantic_auto_sync,
        )

    def search(
        self,
        query: str,
        *,
        creator_sec_uid: str | None,
        tag: str | None,
        limit: int,
    ) -> SemanticSearchResponse:
        results = self.index.search(
            query,
            creator_sec_uid=creator_sec_uid,
            tag=tag,
            limit=limit,
        )
        return SemanticSearchResponse(
            items=[self._search_hit(item) for item in results],
            total=len(results),
            index=self.status(),
        )

    def ask(
        self,
        question: str,
        *,
        creator_sec_uid: str | None,
        tag: str | None,
        max_sources: int | None,
        thinking: bool,
    ) -> AskResponse:
        source_limit = max_sources or self.settings.qa_default_sources
        results = self.index.search(
            question,
            creator_sec_uid=creator_sec_uid,
            tag=tag,
            limit=source_limit,
        )
        sources = [
            self._knowledge_source(item, source_id=f"S{index}")
            for index, item in enumerate(results, start=1)
        ]
        generated = self.answerer.answer(question, sources, thinking=thinking)
        return AskResponse(
            answer=generated.answer,
            insufficient_evidence=generated.insufficient_evidence,
            sources=sources,
            model=self.settings.qa_model if sources else None,
            thinking=thinking,
        )

    @staticmethod
    def _search_hit(item: SemanticResult) -> SemanticSearchHit:
        chunk = item.chunk
        return SemanticSearchHit(
            id=chunk.video_id,
            platform=chunk.platform,
            video_id=chunk.platform_video_id,
            creator_sec_uid=chunk.creator_sec_uid,
            creator_name=chunk.creator_name,
            description=chunk.title,
            summary=chunk.summary,
            tags=list(chunk.tags),
            key_points=[],
            published_at=KnowledgeService._datetime(chunk.published_at),
            status="done",
            updated_at=None,
            match=SemanticMatch(
                source_type=chunk.source_type,
                text=chunk.text,
                start=chunk.start,
                end=chunk.end,
                segment_index=chunk.segment_index,
                segment_count=chunk.segment_count,
                score=item.score,
                semantic_score=item.semantic_score,
                keyword_score=item.keyword_score,
            ),
        )

    @staticmethod
    def _knowledge_source(item: SemanticResult, *, source_id: str) -> KnowledgeSource:
        chunk = item.chunk
        return KnowledgeSource(
            source_id=source_id,
            video_id=chunk.video_id,
            platform_video_id=chunk.platform_video_id,
            creator_sec_uid=chunk.creator_sec_uid,
            creator_name=chunk.creator_name,
            title=chunk.title,
            published_at=KnowledgeService._datetime(chunk.published_at),
            source_type=chunk.source_type,
            start=chunk.start,
            end=chunk.end,
            segment_index=chunk.segment_index,
            segment_count=chunk.segment_count,
            text=chunk.text,
            score=item.score,
        )

    @staticmethod
    def _datetime(value: str | None) -> datetime | None:
        return datetime.fromisoformat(value) if value else None
