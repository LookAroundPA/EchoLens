"""Browser-facing contracts for normalized investment intelligence."""

from __future__ import annotations

from datetime import datetime
from enum import IntEnum
from typing import Literal

from pydantic import Field

from echolens.api.models import ApiModel


TopicStatusFilter = Literal["all", "active", "pending"]
TopicTrendFilter = Literal["all", "new", "rising", "stable", "falling"]
TopicType = Literal["stock", "industry", "index", "commodity", "currency", "macro", "market"]
AssetType = Literal["stock", "etf", "fund", "index", "industry", "commodity", "currency"]
AssetRelationType = Literal["direct", "upstream", "downstream", "benchmark", "related"]


class TopicWindowDays(IntEnum):
    seven = 7
    thirty = 30
HeatTrend = Literal["new", "rising", "stable", "falling"]
DominantStance = Literal["bullish", "bearish", "cautious", "neutral", "unclear", "mixed"]


class TopicSummary(ApiModel):
    id: int
    name: str
    topic_type: str
    status: str


class TopicHeatMetrics(ApiModel):
    window_days: int
    opinion_count: int = 0
    creator_count: int = 0
    explicit_count: int = 0
    inferred_count: int = 0
    change_count: int = 0
    stance_counts: dict[str, int] = Field(default_factory=dict)
    bullish_ratio: float = 0.0
    bearish_ratio: float = 0.0
    cautious_ratio: float = 0.0
    neutral_ratio: float = 0.0
    unclear_ratio: float = 0.0
    dominant_stance: DominantStance = "unclear"
    consensus_ratio: float = 0.0
    weighted_mentions: float = 0.0
    heat_components: dict[str, float] = Field(default_factory=dict)
    heat_score: float = 0.0
    previous_heat_score: float = 0.0
    heat_change: float = 0.0
    trend: HeatTrend = "stable"


class TopicRadarItem(ApiModel):
    topic: TopicSummary
    metrics: TopicHeatMetrics
    latest_published_at: datetime | None = None


class TopicRadarResponse(ApiModel):
    window_days: int
    generated_at: datetime
    items: list[TopicRadarItem]
    total: int


class TopicOpinion(ApiModel):
    id: int
    topic_id: int
    creator_id: int
    creator_platform: str
    creator_sec_uid: str
    creator_name: str | None = None
    video_id: int
    platform_video_id: str
    video_description: str | None = None
    raw_subject: str
    stance: str
    source_type: str
    time_horizon: str
    confidence: str
    conclusion: str
    reasoning: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    evidence_quote: str | None = None
    published_at: datetime
    change_type: str | None = None
    change_summary: str | None = None


class TopicOpinionChange(ApiModel):
    id: int
    topic_id: int
    creator_id: int
    creator_platform: str
    creator_sec_uid: str
    creator_name: str | None = None
    current_opinion_id: int
    current_video_id: int
    change_type: str
    previous_stance: str | None = None
    current_stance: str
    change_summary: str
    detected_at: datetime


class CreatorIntelligenceIdentity(ApiModel):
    id: int
    platform: str
    sec_uid: str
    name: str | None = None


class CreatorTopicOpinion(ApiModel):
    id: int
    topic: TopicSummary
    video_id: int
    platform_video_id: str
    video_description: str | None = None
    raw_subject: str
    stance: str
    source_type: str
    time_horizon: str
    confidence: str
    conclusion: str
    reasoning: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    evidence_quote: str | None = None
    published_at: datetime
    change_type: str | None = None
    change_summary: str | None = None


class CreatorTopicHistorySummary(ApiModel):
    topic: TopicSummary
    opinion_count: int = 0
    explicit_count: int = 0
    inferred_count: int = 0
    change_count: int = 0
    current_stance: str
    current_source_type: str
    current_time_horizon: str
    current_confidence: str
    latest_conclusion: str
    latest_evidence_quote: str | None = None
    latest_opinion_id: int
    latest_video_id: int
    first_published_at: datetime
    latest_published_at: datetime


class CreatorIntelligenceChange(ApiModel):
    id: int
    topic: TopicSummary
    current_opinion_id: int
    current_video_id: int
    change_type: str
    previous_stance: str | None = None
    current_stance: str
    change_summary: str
    detected_at: datetime


class CreatorIntelligenceResponse(ApiModel):
    creator: CreatorIntelligenceIdentity
    topic_count: int = 0
    opinion_count: int = 0
    explicit_count: int = 0
    inferred_count: int = 0
    change_count: int = 0
    topics: list[CreatorTopicHistorySummary] = Field(default_factory=list)
    recent_opinions: list[CreatorTopicOpinion] = Field(default_factory=list)
    recent_changes: list[CreatorIntelligenceChange] = Field(default_factory=list)


class ReferenceAsset(ApiModel):
    id: int
    asset_type: str
    code: str
    name: str
    market: str = ""
    status: str = "active"


class ReferenceAssetListResponse(ApiModel):
    items: list[ReferenceAsset]
    total: int


class ReferenceAssetCreateRequest(ApiModel):
    asset_type: AssetType
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    market: str = Field(default="", max_length=32)


class TopicAssetMapping(ApiModel):
    id: int
    topic_id: int
    asset: ReferenceAsset
    relation_type: str
    note: str | None = None
    source: str
    created_at: datetime
    updated_at: datetime


class TopicAssetListResponse(ApiModel):
    items: list[TopicAssetMapping]
    total: int


class TopicAssetMapRequest(ApiModel):
    asset_id: int = Field(ge=1)
    relation_type: AssetRelationType = "related"
    note: str | None = Field(default=None, max_length=500)


class TopicDetailResponse(ApiModel):
    topic: TopicSummary
    aliases: list[str] = Field(default_factory=list)
    metrics: TopicHeatMetrics
    related_assets: list[TopicAssetMapping] = Field(default_factory=list)
    latest_opinions: list[TopicOpinion] = Field(default_factory=list)
    recent_changes: list[TopicOpinionChange] = Field(default_factory=list)


class TopicHistoryResponse(ApiModel):
    topic: TopicSummary
    items: list[TopicOpinion]
    total: int


class TopicReviewItem(ApiModel):
    topic: TopicSummary
    aliases: list[str] = Field(default_factory=list)
    opinion_count: int = 0
    creator_count: int = 0
    latest_published_at: datetime | None = None


class TopicReviewListResponse(ApiModel):
    items: list[TopicReviewItem]
    total: int


class TopicUpdateRequest(ApiModel):
    canonical_name: str = Field(min_length=1, max_length=255)
    status: Literal["active", "pending"]


class TopicAliasCreateRequest(ApiModel):
    alias: str = Field(min_length=1, max_length=255)


class TopicMergeRequest(ApiModel):
    target_topic_id: int = Field(ge=1)


class TopicMergeResponse(ApiModel):
    source_topic_id: int
    moved_opinion_count: int
    target: TopicReviewItem
