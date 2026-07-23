"""Application service for controlled topic review and merge operations."""

from __future__ import annotations

from typing import Any

from echolens.api.intelligence_models import (
    TopicMergeResponse,
    TopicReviewItem,
    TopicReviewListResponse,
    TopicSummary,
)
from echolens.storage.intelligence_management_repository import (
    IntelligenceManagementRepository,
)


class IntelligenceManagementService:
    """Expose safe topic maintenance without leaking database rows."""

    def __init__(self, repository: IntelligenceManagementRepository) -> None:
        self.repository = repository

    def list_topics(
        self,
        *,
        status: str,
        topic_type: str | None,
        query: str | None,
        limit: int,
        offset: int,
    ) -> TopicReviewListResponse:
        rows, total = self.repository.list_topics(
            status=status,
            topic_type=topic_type,
            query=query,
            limit=limit,
            offset=offset,
        )
        return TopicReviewListResponse(
            items=[self._review_item(row) for row in rows],
            total=total,
        )

    def update_topic(
        self,
        topic_id: int,
        *,
        canonical_name: str,
        status: str,
    ) -> TopicReviewItem | None:
        if self.repository.get_topic_item(topic_id) is None:
            return None
        self.repository.update_topic(
            topic_id,
            canonical_name=canonical_name,
            status=status,
        )
        row = self.repository.get_topic_item(topic_id)
        return None if row is None else self._review_item(row)

    def add_alias(self, topic_id: int, alias: str) -> TopicReviewItem | None:
        if self.repository.get_topic_item(topic_id) is None:
            return None
        self.repository.add_alias(topic_id, alias)
        row = self.repository.get_topic_item(topic_id)
        return None if row is None else self._review_item(row)

    def merge_topics(
        self,
        source_topic_id: int,
        target_topic_id: int,
    ) -> TopicMergeResponse | None:
        if self.repository.get_topic_item(source_topic_id) is None:
            return None
        if self.repository.get_topic_item(target_topic_id) is None:
            raise KeyError(f"Topic {target_topic_id} does not exist")
        moved = self.repository.merge_topics(source_topic_id, target_topic_id)
        target = self.repository.get_topic_item(target_topic_id)
        if target is None:
            raise RuntimeError("Merge target disappeared")
        return TopicMergeResponse(
            source_topic_id=source_topic_id,
            moved_opinion_count=moved,
            target=self._review_item(target),
        )

    @staticmethod
    def _review_item(row: dict[str, Any]) -> TopicReviewItem:
        return TopicReviewItem(
            topic=TopicSummary(
                id=int(row["id"]),
                name=str(row["canonical_name"]),
                topic_type=str(row["topic_type"]),
                status=str(row["status"]),
            ),
            aliases=[str(value) for value in row.get("aliases", [])],
            opinion_count=int(row.get("opinion_count") or 0),
            creator_count=int(row.get("creator_count") or 0),
            latest_published_at=row.get("latest_published_at"),
        )
