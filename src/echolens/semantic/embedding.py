"""FastEmbed wrapper used by the local semantic index."""

from __future__ import annotations

import math
from typing import Any, Iterable

from echolens.core.config import Settings, get_settings


class FastEmbedder:
    """Generate normalized CPU embeddings without a vector service."""

    def __init__(self, settings: Settings | None = None, model: Any | None = None) -> None:
        self.settings = settings or get_settings()
        self._model = model

    @property
    def model_name(self) -> str:
        return self.settings.semantic_model

    def embed_documents(self, texts: Iterable[str]) -> list[tuple[float, ...]]:
        materialized = [text.strip() for text in texts]
        if any(not text for text in materialized):
            raise ValueError("Semantic documents must not be empty")
        return [self._normalize(vector) for vector in self._get_model().embed(materialized)]

    def embed_query(self, query: str) -> tuple[float, ...]:
        normalized = query.strip()
        if not normalized:
            raise ValueError("Semantic query must not be empty")
        prompt = f"{self.settings.semantic_query_prefix}{normalized}"
        return self.embed_documents([prompt])[0]

    def _get_model(self) -> Any:
        if self._model is None:
            from fastembed import TextEmbedding

            cache_dir = self.settings.semantic_model_cache_dir
            cache_dir.mkdir(parents=True, exist_ok=True)
            self._model = TextEmbedding(
                model_name=self.settings.semantic_model,
                cache_dir=str(cache_dir),
            )
        return self._model

    @staticmethod
    def _normalize(vector: Any) -> tuple[float, ...]:
        values = tuple(float(value) for value in vector)
        norm = math.sqrt(sum(value * value for value in values))
        if norm <= 0:
            raise ValueError("Embedding model returned a zero vector")
        return tuple(value / norm for value in values)
