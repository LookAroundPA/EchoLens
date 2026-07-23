"""Deterministic topic normalization with a deliberately small alias seed set."""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata


@dataclass(frozen=True)
class SeedTopic:
    """One maintained canonical topic and its accepted aliases."""

    topic_type: str
    canonical_name: str
    aliases: tuple[str, ...]


SEED_TOPICS: tuple[SeedTopic, ...] = (
    SeedTopic(
        topic_type="industry",
        canonical_name="人工智能",
        aliases=(
            "AI",
            "人工智能",
            "AI产业",
            "AI行业",
            "AI产业链",
            "人工智能产业链",
            "中国AI产业",
        ),
    ),
    SeedTopic(
        topic_type="market",
        canonical_name="A股",
        aliases=("A股", "A股市场", "A股市场整体", "中国A股"),
    ),
)


def normalize_topic_name(value: str) -> str:
    """Return a comparison key while preserving Chinese characters and letters."""

    normalized = unicodedata.normalize("NFKC", str(value)).strip().lower()
    return re.sub(r"[\W_]+", "", normalized, flags=re.UNICODE)


def find_seed_topic(subject: str, subject_type: str) -> SeedTopic | None:
    """Resolve a raw subject against the maintained seed aliases."""

    lookup = normalize_topic_name(subject)
    for topic in SEED_TOPICS:
        if topic.topic_type != subject_type:
            continue
        candidates = (topic.canonical_name, *topic.aliases)
        if any(normalize_topic_name(candidate) == lookup for candidate in candidates):
            return topic
    return None
