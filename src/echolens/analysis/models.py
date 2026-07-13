"""Structured content-analysis results."""

from pydantic import BaseModel, Field, field_validator


class AnalysisResult(BaseModel):
    """Normalized result returned by the configured LLM."""

    summary: str = Field(min_length=1)
    tags: list[str] = Field(min_length=1, max_length=12)
    key_points: list[str] = Field(min_length=1, max_length=20)

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
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            item = str(value).strip()
            if item and item not in seen:
                normalized.append(item)
                seen.add(item)
        if not normalized:
            raise ValueError("list must contain at least one non-empty item")
        return normalized
