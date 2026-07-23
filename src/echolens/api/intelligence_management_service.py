"""Application service for controlled topic review and merge operations."""

from __future__ import annotations

from typing import Any

from echolens.api.intelligence_models import (
    ReferenceAsset,
    ReferenceAssetListResponse,
    TopicAssetListResponse,
    TopicAssetMapping,
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

    def list_assets(
        self,
        *,
        asset_type: str | None,
        query: str | None,
        limit: int,
        offset: int,
    ) -> ReferenceAssetListResponse:
        rows, total = self.repository.list_assets(
            asset_type=asset_type,
            query=query,
            limit=limit,
            offset=offset,
        )
        return ReferenceAssetListResponse(
            items=[self._asset(row) for row in rows],
            total=total,
        )

    def create_asset(
        self,
        *,
        asset_type: str,
        code: str,
        name: str,
        market: str,
    ) -> ReferenceAsset:
        return self._asset(
            self.repository.create_asset(
                asset_type=asset_type,
                code=code,
                name=name,
                market=market,
            )
        )

    def list_topic_assets(self, topic_id: int) -> TopicAssetListResponse | None:
        if self.repository.get_topic_item(topic_id) is None:
            return None
        rows = self.repository.list_topic_assets(topic_id)
        return TopicAssetListResponse(
            items=[self._asset_mapping(row) for row in rows],
            total=len(rows),
        )

    def map_asset(
        self,
        topic_id: int,
        *,
        asset_id: int,
        relation_type: str,
        note: str | None,
    ) -> TopicAssetListResponse | None:
        if self.repository.get_topic_item(topic_id) is None:
            return None
        self.repository.map_asset(
            topic_id,
            asset_id=asset_id,
            relation_type=relation_type,
            note=note,
        )
        return self.list_topic_assets(topic_id)

    def remove_asset_mapping(
        self,
        topic_id: int,
        mapping_id: int,
    ) -> TopicAssetListResponse | None:
        if self.repository.get_topic_item(topic_id) is None:
            return None
        if not self.repository.remove_asset_mapping(topic_id, mapping_id):
            raise KeyError(f"Asset mapping {mapping_id} does not exist")
        return self.list_topic_assets(topic_id)

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
    def _asset(row: dict[str, Any]) -> ReferenceAsset:
        return ReferenceAsset(
            id=int(row["id"]),
            asset_type=str(row["asset_type"]),
            code=str(row["code"]),
            name=str(row["name"]),
            market=str(row.get("market") or ""),
            status=str(row.get("status") or "active"),
        )

    @classmethod
    def _asset_mapping(cls, row: dict[str, Any]) -> TopicAssetMapping:
        return TopicAssetMapping(
            id=int(row["id"]),
            topic_id=int(row["topic_id"]),
            asset=ReferenceAsset(
                id=int(row["asset_id"]),
                asset_type=str(row["asset_type"]),
                code=str(row["code"]),
                name=str(row["name"]),
                market=str(row.get("market") or ""),
                status=str(row.get("asset_status") or "active"),
            ),
            relation_type=str(row["relation_type"]),
            note=row.get("note"),
            source=str(row["source"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
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
