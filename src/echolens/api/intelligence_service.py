"""Application service for topic history and explainable market-radar metrics."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any

from echolens.api.intelligence_models import (
    CreatorIntelligenceChange,
    CreatorIntelligenceIdentity,
    CreatorIntelligenceResponse,
    CreatorTopicHistorySummary,
    CreatorTopicOpinion,
    ReferenceAsset,
    TopicAssetMapping,
    TopicDetailResponse,
    TopicHeatMetrics,
    TopicHistoryResponse,
    TopicOpinion,
    TopicOpinionChange,
    TopicRadarItem,
    TopicRadarResponse,
    TopicSummary,
)
from echolens.api.models import json_string_list
from echolens.storage.intelligence_query_repository import IntelligenceQueryRepository


STANCE_VALUES = (
    "strong_bullish",
    "bullish",
    "neutral",
    "cautious",
    "bearish",
    "strong_bearish",
    "unclear",
)
SOURCE_WEIGHTS = {"explicit": 1.0, "inferred": 0.6}


class IntelligenceApiService:
    """Build traceable topic timelines and explainable heat rankings."""

    def __init__(self, repository: IntelligenceQueryRepository) -> None:
        self.repository = repository

    def radar(
        self,
        *,
        window_days: int,
        topic_status: str,
        topic_type: str | None,
        trend_filter: str,
        limit: int,
        now: datetime | None = None,
    ) -> TopicRadarResponse:
        generated_at = now or datetime.now()
        current_start = generated_at - timedelta(days=window_days)
        previous_start = current_start - timedelta(days=window_days)
        rows = self.repository.list_opinions_between(
            previous_start,
            generated_at,
            topic_status=topic_status,
            topic_type=topic_type,
        )
        changes = self.repository.list_changes_between(
            previous_start,
            generated_at,
            topic_status=topic_status,
            topic_type=topic_type,
        )
        rows_by_topic: dict[int, list[dict[str, Any]]] = defaultdict(list)
        changes_by_topic: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            rows_by_topic[int(row["topic_id"])].append(row)
        for row in changes:
            changes_by_topic[int(row["topic_id"])].append(row)

        items: list[TopicRadarItem] = []
        for topic_id, topic_rows in rows_by_topic.items():
            current_rows = [row for row in topic_rows if row["published_at"] >= current_start]
            previous_rows = [row for row in topic_rows if row["published_at"] < current_start]
            topic_changes = changes_by_topic.get(topic_id, [])
            current_changes = [row for row in topic_changes if row["detected_at"] >= current_start]
            previous_changes = [row for row in topic_changes if row["detected_at"] < current_start]
            sample = (current_rows or previous_rows)[-1]
            metrics = self._build_metrics(
                current_rows,
                current_changes,
                previous_rows,
                previous_changes,
                window_days=window_days,
            )
            if trend_filter != "all" and metrics.trend != trend_filter:
                continue
            latest_rows = current_rows or previous_rows
            items.append(
                TopicRadarItem(
                    topic=TopicSummary(
                        id=topic_id,
                        name=str(sample["canonical_name"]),
                        topic_type=str(sample["topic_type"]),
                        status=str(sample["topic_status"]),
                    ),
                    metrics=metrics,
                    latest_published_at=max(row["published_at"] for row in latest_rows),
                )
            )

        if trend_filter == "falling":
            items.sort(
                key=lambda item: (
                    item.metrics.heat_change,
                    -item.metrics.previous_heat_score,
                    item.topic.name,
                )
            )
        elif trend_filter in {"new", "rising"}:
            items.sort(
                key=lambda item: (
                    -item.metrics.heat_change,
                    -item.metrics.heat_score,
                    item.topic.name,
                )
            )
        else:
            items.sort(
                key=lambda item: (
                    -item.metrics.heat_score,
                    -item.metrics.creator_count,
                    -item.metrics.opinion_count,
                    item.topic.name,
                )
            )
        total = len(items)
        return TopicRadarResponse(
            window_days=window_days,
            generated_at=generated_at,
            items=items[:limit],
            total=total,
        )

    def topic_detail(
        self,
        topic_id: int,
        *,
        window_days: int,
        opinion_limit: int,
        now: datetime | None = None,
    ) -> TopicDetailResponse | None:
        topic_row = self.repository.get_topic(topic_id)
        if topic_row is None:
            return None
        generated_at = now or datetime.now()
        current_start = generated_at - timedelta(days=window_days)
        previous_start = current_start - timedelta(days=window_days)
        rows = self.repository.list_opinions_between(
            previous_start,
            generated_at,
            topic_id=topic_id,
        )
        changes = self.repository.list_changes_between(
            previous_start,
            generated_at,
            topic_id=topic_id,
        )
        current_rows = [row for row in rows if row["published_at"] >= current_start]
        previous_rows = [row for row in rows if row["published_at"] < current_start]
        current_changes = [row for row in changes if row["detected_at"] >= current_start]
        previous_changes = [row for row in changes if row["detected_at"] < current_start]
        opinion_rows, _ = self.repository.list_topic_opinions(topic_id, limit=opinion_limit)
        return TopicDetailResponse(
            topic=self._topic_from_row(topic_row),
            aliases=self.repository.list_aliases(topic_id),
            metrics=self._build_metrics(
                current_rows,
                current_changes,
                previous_rows,
                previous_changes,
                window_days=window_days,
            ),
            related_assets=[
                self._asset_mapping_from_row(row)
                for row in self.repository.list_topic_assets(topic_id)
            ],
            latest_opinions=[self._opinion_from_row(row) for row in opinion_rows],
            recent_changes=[
                self._change_from_row(row)
                for row in self.repository.list_topic_changes(topic_id, limit=opinion_limit)
            ],
        )

    def topic_history(
        self,
        topic_id: int,
        *,
        creator_sec_uid: str | None,
        limit: int,
        offset: int,
    ) -> TopicHistoryResponse | None:
        topic_row = self.repository.get_topic(topic_id)
        if topic_row is None:
            return None
        rows, total = self.repository.list_topic_opinions(
            topic_id,
            creator_sec_uid=creator_sec_uid,
            limit=limit,
            offset=offset,
        )
        return TopicHistoryResponse(
            topic=self._topic_from_row(topic_row),
            items=[self._opinion_from_row(row) for row in rows],
            total=total,
        )

    def creator_intelligence(
        self,
        creator_sec_uid: str,
        *,
        topic_limit: int,
        opinion_limit: int,
        change_limit: int,
    ) -> CreatorIntelligenceResponse | None:
        creator_row = self.repository.get_creator(creator_sec_uid)
        if creator_row is None:
            return None
        rows = self.repository.list_creator_opinions(creator_sec_uid)
        changes = self.repository.list_creator_changes(creator_sec_uid)
        rows_by_topic: dict[int, list[dict[str, Any]]] = defaultdict(list)
        changes_by_topic: Counter[int] = Counter()
        for row in rows:
            rows_by_topic[int(row["topic_id"])].append(row)
        for row in changes:
            changes_by_topic[int(row["topic_id"])] += 1

        topics: list[CreatorTopicHistorySummary] = []
        for topic_rows in rows_by_topic.values():
            latest = topic_rows[0]
            topics.append(
                CreatorTopicHistorySummary(
                    topic=self._topic_from_intelligence_row(latest),
                    opinion_count=len(topic_rows),
                    explicit_count=sum(str(row["source_type"]) == "explicit" for row in topic_rows),
                    inferred_count=sum(str(row["source_type"]) == "inferred" for row in topic_rows),
                    change_count=changes_by_topic[int(latest["topic_id"])],
                    current_stance=str(latest["stance"]),
                    current_source_type=str(latest["source_type"]),
                    current_time_horizon=str(latest["time_horizon"]),
                    current_confidence=str(latest["confidence"]),
                    latest_conclusion=str(latest["conclusion"]),
                    latest_evidence_quote=latest.get("evidence_quote"),
                    latest_opinion_id=int(latest["id"]),
                    latest_video_id=int(latest["video_id"]),
                    first_published_at=min(row["published_at"] for row in topic_rows),
                    latest_published_at=max(row["published_at"] for row in topic_rows),
                )
            )
        topics.sort(
            key=lambda item: (
                item.latest_published_at,
                item.opinion_count,
                item.topic.id,
            ),
            reverse=True,
        )
        explicit_count = sum(str(row["source_type"]) == "explicit" for row in rows)
        inferred_count = sum(str(row["source_type"]) == "inferred" for row in rows)
        return CreatorIntelligenceResponse(
            creator=CreatorIntelligenceIdentity(
                id=int(creator_row["id"]),
                platform=str(creator_row["platform"]),
                sec_uid=str(creator_row["sec_uid"]),
                name=creator_row.get("creator_name"),
            ),
            topic_count=len(topics),
            opinion_count=len(rows),
            explicit_count=explicit_count,
            inferred_count=inferred_count,
            change_count=len(changes),
            topics=topics[:topic_limit],
            recent_opinions=[
                self._creator_opinion_from_row(row) for row in rows[:opinion_limit]
            ],
            recent_changes=[
                self._creator_change_from_row(row) for row in changes[:change_limit]
            ],
        )

    def _build_metrics(
        self,
        current_rows: list[dict[str, Any]],
        current_changes: list[dict[str, Any]],
        previous_rows: list[dict[str, Any]],
        previous_changes: list[dict[str, Any]],
        *,
        window_days: int,
    ) -> TopicHeatMetrics:
        current = self._period_stats(current_rows, current_changes)
        previous = self._period_stats(previous_rows, previous_changes)
        heat_score = float(current["heat_score"])
        previous_heat_score = float(previous["heat_score"])
        heat_change = round(heat_score - previous_heat_score, 2)
        if previous_heat_score == 0 and heat_score > 0:
            trend = "new"
        else:
            threshold = max(1.0, previous_heat_score * 0.1)
            if heat_change >= threshold:
                trend = "rising"
            elif heat_change <= -threshold:
                trend = "falling"
            else:
                trend = "stable"
        return TopicHeatMetrics(
            window_days=window_days,
            opinion_count=int(current["opinion_count"]),
            creator_count=int(current["creator_count"]),
            explicit_count=int(current["explicit_count"]),
            inferred_count=int(current["inferred_count"]),
            change_count=int(current["change_count"]),
            stance_counts=dict(current["stance_counts"]),
            bullish_ratio=float(current["bullish_ratio"]),
            bearish_ratio=float(current["bearish_ratio"]),
            cautious_ratio=float(current["cautious_ratio"]),
            neutral_ratio=float(current["neutral_ratio"]),
            unclear_ratio=float(current["unclear_ratio"]),
            dominant_stance=str(current["dominant_stance"]),
            consensus_ratio=float(current["consensus_ratio"]),
            weighted_mentions=float(current["weighted_mentions"]),
            heat_components=dict(current["heat_components"]),
            heat_score=heat_score,
            previous_heat_score=previous_heat_score,
            heat_change=heat_change,
            trend=trend,
        )

    @staticmethod
    def _period_stats(
        rows: list[dict[str, Any]],
        changes: list[dict[str, Any]],
    ) -> dict[str, Any]:
        latest_by_creator: dict[int, dict[str, Any]] = {}
        mentions_by_creator_day: dict[tuple[int, object], float] = defaultdict(float)
        explicit_count = inferred_count = 0
        for row in rows:
            creator_id = int(row["creator_id"])
            latest_by_creator[creator_id] = row
            source_type = str(row["source_type"])
            explicit_count += int(source_type == "explicit")
            inferred_count += int(source_type == "inferred")
            day_key = (creator_id, row["published_at"].date())
            mentions_by_creator_day[day_key] += SOURCE_WEIGHTS.get(source_type, 0.5)

        stance_counts = Counter({stance: 0 for stance in STANCE_VALUES})
        for row in latest_by_creator.values():
            stance_counts[str(row["stance"])] += 1
        creator_count = len(latest_by_creator)
        bullish = stance_counts["strong_bullish"] + stance_counts["bullish"]
        bearish = stance_counts["strong_bearish"] + stance_counts["bearish"]
        bucket_counts = {
            "bullish": bullish,
            "bearish": bearish,
            "cautious": stance_counts["cautious"],
            "neutral": stance_counts["neutral"],
            "unclear": stance_counts["unclear"],
        }
        if creator_count:
            max_count = max(bucket_counts.values())
            winners = [name for name, count in bucket_counts.items() if count == max_count]
            consensus_ratio = round(max_count / creator_count, 4)
            dominant_stance = winners[0] if len(winners) == 1 and consensus_ratio >= 0.5 else "mixed"
        else:
            consensus_ratio = 0.0
            dominant_stance = "unclear"

        weighted_mentions = round(
            sum(min(weight, 1.5) for weight in mentions_by_creator_day.values()),
            2,
        )
        change_count = len(changes)
        capped_changes = min(change_count, creator_count * 2)
        creator_score = round(creator_count * 3.0, 2)
        mention_score = weighted_mentions
        change_score = round(capped_changes * 1.5, 2)
        heat_score = round(creator_score + mention_score + change_score, 2)
        denominator = creator_count or 1
        return {
            "opinion_count": len(rows),
            "creator_count": creator_count,
            "explicit_count": explicit_count,
            "inferred_count": inferred_count,
            "change_count": change_count,
            "stance_counts": dict(stance_counts),
            "bullish_ratio": round(bullish / denominator, 4) if creator_count else 0.0,
            "bearish_ratio": round(bearish / denominator, 4) if creator_count else 0.0,
            "cautious_ratio": round(stance_counts["cautious"] / denominator, 4) if creator_count else 0.0,
            "neutral_ratio": round(stance_counts["neutral"] / denominator, 4) if creator_count else 0.0,
            "unclear_ratio": round(stance_counts["unclear"] / denominator, 4) if creator_count else 0.0,
            "dominant_stance": dominant_stance,
            "consensus_ratio": consensus_ratio,
            "weighted_mentions": weighted_mentions,
            "heat_components": {
                "creator_score": creator_score,
                "mention_score": mention_score,
                "change_score": change_score,
            },
            "heat_score": heat_score,
        }

    @staticmethod
    def _topic_from_row(row: dict[str, Any]) -> TopicSummary:
        return TopicSummary(
            id=int(row["id"]),
            name=str(row["canonical_name"]),
            topic_type=str(row["topic_type"]),
            status=str(row["status"]),
        )

    @staticmethod
    def _topic_from_intelligence_row(row: dict[str, Any]) -> TopicSummary:
        return TopicSummary(
            id=int(row["topic_id"]),
            name=str(row["canonical_name"]),
            topic_type=str(row["topic_type"]),
            status=str(row["topic_status"]),
        )

    @classmethod
    def _creator_opinion_from_row(cls, row: dict[str, Any]) -> CreatorTopicOpinion:
        return CreatorTopicOpinion(
            id=int(row["id"]),
            topic=cls._topic_from_intelligence_row(row),
            video_id=int(row["video_id"]),
            platform_video_id=str(row["platform_video_id"]),
            video_description=row.get("video_description"),
            raw_subject=str(row["raw_subject"]),
            stance=str(row["stance"]),
            source_type=str(row["source_type"]),
            time_horizon=str(row["time_horizon"]),
            confidence=str(row["confidence"]),
            conclusion=str(row["conclusion"]),
            reasoning=json_string_list(row.get("reasoning_json")),
            risks=json_string_list(row.get("risks_json")),
            evidence_quote=row.get("evidence_quote"),
            published_at=row["published_at"],
            change_type=row.get("change_type"),
            change_summary=row.get("change_summary"),
        )

    @classmethod
    def _creator_change_from_row(cls, row: dict[str, Any]) -> CreatorIntelligenceChange:
        return CreatorIntelligenceChange(
            id=int(row["id"]),
            topic=cls._topic_from_intelligence_row(row),
            current_opinion_id=int(row["current_opinion_id"]),
            current_video_id=int(row["current_video_id"]),
            change_type=str(row["change_type"]),
            previous_stance=row.get("previous_stance"),
            current_stance=str(row["current_stance"]),
            change_summary=str(row["change_summary"]),
            detected_at=row["detected_at"],
        )

    @staticmethod
    def _asset_mapping_from_row(row: dict[str, Any]) -> TopicAssetMapping:
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
    def _opinion_from_row(row: dict[str, Any]) -> TopicOpinion:
        return TopicOpinion(
            id=int(row["id"]),
            topic_id=int(row["topic_id"]),
            creator_id=int(row["creator_id"]),
            creator_platform=str(row["creator_platform"]),
            creator_sec_uid=str(row["creator_sec_uid"]),
            creator_name=row.get("creator_name"),
            video_id=int(row["video_id"]),
            platform_video_id=str(row["platform_video_id"]),
            video_description=row.get("video_description"),
            raw_subject=str(row["raw_subject"]),
            stance=str(row["stance"]),
            source_type=str(row["source_type"]),
            time_horizon=str(row["time_horizon"]),
            confidence=str(row["confidence"]),
            conclusion=str(row["conclusion"]),
            reasoning=json_string_list(row.get("reasoning_json")),
            risks=json_string_list(row.get("risks_json")),
            evidence_quote=row.get("evidence_quote"),
            published_at=row["published_at"],
            change_type=row.get("change_type"),
            change_summary=row.get("change_summary"),
        )

    @staticmethod
    def _change_from_row(row: dict[str, Any]) -> TopicOpinionChange:
        return TopicOpinionChange(
            id=int(row["id"]),
            topic_id=int(row["topic_id"]),
            creator_id=int(row["creator_id"]),
            creator_platform=str(row["creator_platform"]),
            creator_sec_uid=str(row["creator_sec_uid"]),
            creator_name=row.get("creator_name"),
            current_opinion_id=int(row["current_opinion_id"]),
            current_video_id=int(row["current_video_id"]),
            change_type=str(row["change_type"]),
            previous_stance=row.get("previous_stance"),
            current_stance=str(row["current_stance"]),
            change_summary=str(row["change_summary"]),
            detected_at=row["detected_at"],
        )
