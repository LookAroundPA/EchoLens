"""Structured content-analysis results."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class MarketInsight(BaseModel):
    """One structured market conclusion grounded in the transcript."""

    subject: str = Field(min_length=1, max_length=255)
    subject_type: Literal["stock", "industry", "index", "commodity", "currency", "macro", "market"]
    stance: Literal[
        "strong_bullish",
        "bullish",
        "neutral",
        "cautious",
        "bearish",
        "strong_bearish",
        "unclear",
    ]
    conclusion: str = Field(min_length=1)
    source_type: Literal["explicit", "inferred"]
    time_horizon: Literal["intraday", "short_term", "medium_term", "long_term", "unspecified"]
    confidence: Literal["high", "medium", "low"]
    reasoning: list[str] = Field(default_factory=list, max_length=10)
    risks: list[str] = Field(default_factory=list, max_length=10)
    evidence_quote: str | None = None

    @field_validator("subject", "conclusion")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("reasoning", "risks")
    @classmethod
    def normalize_insight_lists(cls, values: list[str]) -> list[str]:
        return _normalize_string_list(values)

    @field_validator("evidence_quote")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class AnalysisResult(BaseModel):
    """Normalized result returned by the configured LLM."""

    summary: str = Field(min_length=1)
    tags: list[str] = Field(min_length=1, max_length=12)
    key_points: list[str] = Field(min_length=1, max_length=20)
    market_insights: list[MarketInsight] = Field(default_factory=list, max_length=20)

    @field_validator("summary")
    @classmethod
    def normalize_summary(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("summary must not be empty")
        return normalized

    @field_validator("tags", "key_points")
    @classmethod
    def normalize_list(cls, values: list[str]) -> list[str]:
        normalized = _normalize_string_list(values)
        if not normalized:
            raise ValueError("list must contain at least one non-empty item")
        return normalized


def _normalize_string_list(values: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value).strip()
        if item and item not in seen:
            normalized.append(item)
            seen.add(item)
    return normalized
