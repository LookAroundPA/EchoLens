"""Deterministic classification of creator topic-opinion changes."""

from __future__ import annotations


_DIRECTIONAL_SCORES = {
    "strong_bearish": -2,
    "bearish": -1,
    "neutral": 0,
    "bullish": 1,
    "strong_bullish": 2,
}


def detect_opinion_change(
    previous_stance: str | None,
    current_stance: str,
    *,
    gap_days: int | None = None,
    resume_after_days: int = 90,
) -> str | None:
    """Classify a meaningful change between two ordered opinions."""

    if previous_stance is None:
        return "first_mention"
    if previous_stance == current_stance:
        if gap_days is not None and gap_days >= resume_after_days:
            return "resumed_attention"
        return None
    if current_stance == "cautious":
        return "became_cautious"
    if current_stance == "neutral":
        return "became_neutral"
    if current_stance == "unclear":
        return "became_unclear"

    previous_score = _DIRECTIONAL_SCORES.get(previous_stance)
    current_score = _DIRECTIONAL_SCORES.get(current_stance)
    if previous_score is None or current_score is None:
        return "stance_changed"
    if previous_score * current_score < 0:
        return "reversal"
    if previous_score == 0 or current_score == 0:
        return "stance_changed"
    if abs(current_score) > abs(previous_score):
        return "strengthened"
    if abs(current_score) < abs(previous_score):
        return "weakened"
    return "stance_changed"


def build_change_summary(
    change_type: str,
    previous_stance: str | None,
    current_stance: str,
) -> str:
    """Build an auditable, model-free summary for one change record."""

    if change_type == "first_mention":
        return f"首次形成主题观点：{current_stance}"
    if change_type == "resumed_attention":
        return f"长时间未提及后重新关注，当前立场：{current_stance}"
    return f"立场由 {previous_stance or '无'} 变为 {current_stance}（{change_type}）"
