"""Incremental local semantic indexing and hybrid retrieval."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import math
import re
from threading import Lock
from typing import Any, Protocol

from echolens.api.models import json_string_list, published_datetime, transcript_segments
from echolens.core.config import Settings, get_settings
from echolens.semantic.embedding import FastEmbedder
from echolens.semantic.store import SemanticStore, SemanticStoreStatus, StoredChunk
from echolens.storage.mysql import mysql_connection
from echolens.storage.semantic_repository import SemanticSourceRepository


_NORMALIZE_PATTERN = re.compile(r"[^0-9a-z\u3400-\u9fff]+", re.IGNORECASE)


class SemanticSourceProvider(Protocol):
    def list_indexable_videos(self) -> list[dict[str, Any]]: ...

    def get_indexable_video(self, video_db_id: int) -> dict[str, Any] | None: ...


class MysqlSemanticSourceProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def list_indexable_videos(self) -> list[dict[str, Any]]:
        with mysql_connection(self.settings) as connection:
            return SemanticSourceRepository(connection).list_indexable_videos()

    def get_indexable_video(self, video_db_id: int) -> dict[str, Any] | None:
        with mysql_connection(self.settings) as connection:
            return SemanticSourceRepository(connection).get_indexable_video(video_db_id)


@dataclass(frozen=True)
class IndexSyncResult:
    discovered: int
    indexed: int
    skipped: int
    removed: int
    chunks: int
    rebuilt: bool

    def as_dict(self) -> dict[str, int | bool]:
        return {
            "discovered": self.discovered,
            "indexed": self.indexed,
            "skipped": self.skipped,
            "removed": self.removed,
            "chunks": self.chunks,
            "rebuilt": self.rebuilt,
        }


@dataclass(frozen=True)
class SemanticResult:
    chunk: StoredChunk
    score: float
    semantic_score: float
    keyword_score: float


@dataclass(frozen=True)
class _ChunkSpec:
    chunk_id: str
    source_type: str
    segment_index: int | None
    segment_count: int
    start: float | None
    end: float | None
    text: str
    document: str


class SemanticIndexService:
    """Keep a small local vector index synchronized with completed videos."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        source: SemanticSourceProvider | None = None,
        embedder: FastEmbedder | None = None,
        store: SemanticStore | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.source = source or MysqlSemanticSourceProvider(self.settings)
        self.embedder = embedder or FastEmbedder(self.settings)
        self.store = store or SemanticStore(self.settings.semantic_index_path)
        self._sync_lock = Lock()

    def status(self) -> SemanticStoreStatus:
        return self.store.status()

    def sync(self, *, rebuild: bool = False) -> IndexSyncResult:
        with self._sync_lock:
            rows = self.source.list_indexable_videos()
            current_status = self.store.status()
            effective_rebuild = rebuild or (
                current_status.model is not None
                and current_status.model != self.settings.semantic_model
            )
            if effective_rebuild:
                self.store.clear()

            fingerprints = self.store.fingerprints()
            indexed = skipped = chunks = 0
            current_ids: set[int] = set()
            for row in rows:
                video_id = int(row["id"])
                current_ids.add(video_id)
                fingerprint = self._fingerprint(row)
                if fingerprints.get(video_id) == fingerprint:
                    skipped += 1
                    continue
                chunks += self._index_row(row, fingerprint)
                indexed += 1

            removed = self.store.remove_missing_videos(current_ids)
            return IndexSyncResult(
                discovered=len(rows),
                indexed=indexed,
                skipped=skipped,
                removed=removed,
                chunks=chunks,
                rebuilt=effective_rebuild,
            )

    def index_video(self, video_db_id: int) -> IndexSyncResult:
        with self._sync_lock:
            row = self.source.get_indexable_video(video_db_id)
            if row is None:
                self.store.remove_video(video_db_id)
                return IndexSyncResult(0, 0, 0, 1, 0, False)
            fingerprint = self._fingerprint(row)
            if self.store.fingerprints().get(video_db_id) == fingerprint:
                return IndexSyncResult(1, 0, 1, 0, 0, False)
            count = self._index_row(row, fingerprint)
            return IndexSyncResult(1, 1, 0, 0, count, False)

    def search(
        self,
        query: str,
        *,
        creator_sec_uid: str | None = None,
        tag: str | None = None,
        limit: int = 20,
        ensure_synced: bool | None = None,
    ) -> list[SemanticResult]:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("Search query must not be empty")
        should_sync = self.settings.semantic_auto_sync if ensure_synced is None else ensure_synced
        if should_sync:
            self.sync()
        if not self.store.status().ready:
            return []

        query_vector = self.embedder.embed_query(normalized_query)
        candidates = self.store.candidates(creator_sec_uid)
        requested_tag = tag.strip().casefold() if tag else None
        scored: list[SemanticResult] = []
        for chunk in candidates:
            if requested_tag and requested_tag not in {item.casefold() for item in chunk.tags}:
                continue
            semantic_score = max(-1.0, min(1.0, self._dot(query_vector, chunk.vector)))
            keyword_score = self._keyword_score(normalized_query, chunk)
            combined = max(0.0, semantic_score) * 0.82 + keyword_score * 0.18
            if chunk.source_type == "transcript":
                combined += 0.015
            if combined < self.settings.semantic_min_score:
                continue
            scored.append(
                SemanticResult(
                    chunk=chunk,
                    score=round(min(1.0, combined), 4),
                    semantic_score=round(semantic_score, 4),
                    keyword_score=round(keyword_score, 4),
                )
            )

        scored.sort(
            key=lambda item: (
                item.score,
                item.keyword_score,
                item.chunk.source_type == "transcript",
                item.chunk.start is not None,
            ),
            reverse=True,
        )
        per_video: dict[int, int] = defaultdict(int)
        results: list[SemanticResult] = []
        for item in scored:
            if per_video[item.chunk.video_id] >= self.settings.semantic_max_chunks_per_video:
                continue
            results.append(item)
            per_video[item.chunk.video_id] += 1
            if len(results) >= limit:
                break
        return results

    def _index_row(self, row: dict[str, Any], fingerprint: str) -> int:
        specs = self._chunk_specs(row)
        vectors = self.embedder.embed_documents(spec.document for spec in specs)
        published = published_datetime(row.get("source_create_time"))
        title = str(row.get("description") or row.get("summary") or f"视频 {row['video_id']}")
        tags = tuple(json_string_list(row.get("tags_json")))
        stored = [
            StoredChunk(
                chunk_id=spec.chunk_id,
                video_id=int(row["id"]),
                platform=str(row["platform"]),
                platform_video_id=str(row["video_id"]),
                creator_sec_uid=str(row["creator_sec_uid"]),
                creator_name=(str(row["creator_name"]) if row.get("creator_name") else None),
                title=title,
                summary=(str(row["summary"]) if row.get("summary") else None),
                tags=tags,
                published_at=published.isoformat() if published else None,
                source_type=spec.source_type,
                segment_index=spec.segment_index,
                segment_count=spec.segment_count,
                start=spec.start,
                end=spec.end,
                text=spec.text,
                vector=vectors[index],
            )
            for index, spec in enumerate(specs)
        ]
        return self.store.replace_video(
            video_id=int(row["id"]),
            fingerprint=fingerprint,
            chunks=stored,
            model=self.settings.semantic_model,
        )

    def _chunk_specs(self, row: dict[str, Any]) -> list[_ChunkSpec]:
        video_id = int(row["id"])
        title = str(row.get("description") or row.get("summary") or f"视频 {row['video_id']}")
        summary = str(row.get("summary") or "").strip()
        tags = json_string_list(row.get("tags_json"))
        points = json_string_list(row.get("key_points_json"))
        segments = transcript_segments(row.get("segments_json"))
        context = [f"视频：{title}"]
        if summary:
            context.append(f"摘要：{summary}")
        if tags:
            context.append(f"主题：{'、'.join(tags)}")
        prefix = "\n".join(context)

        specs: list[_ChunkSpec] = []
        index = 0
        while index < len(segments):
            window = []
            character_count = 0
            while index + len(window) < len(segments) and len(window) < self.settings.semantic_chunk_max_segments:
                segment = segments[index + len(window)]
                next_count = character_count + len(segment.text)
                if window and next_count > self.settings.semantic_chunk_max_chars:
                    break
                window.append(segment)
                character_count = next_count
            if not window:
                index += 1
                continue
            text = self._join_text([segment.text for segment in window])
            specs.append(
                _ChunkSpec(
                    chunk_id=f"{video_id}:transcript:{index}:{len(window)}",
                    source_type="transcript",
                    segment_index=index,
                    segment_count=len(window),
                    start=float(window[0].start),
                    end=float(window[-1].end),
                    text=text,
                    document=f"{prefix}\n转写片段：{text}",
                )
            )
            index += max(1, len(window) - 1)

        analysis_parts = []
        if summary:
            analysis_parts.append(summary)
        analysis_parts.extend(points)
        analysis_text = self._join_text(analysis_parts)
        if analysis_text:
            specs.append(
                _ChunkSpec(
                    chunk_id=f"{video_id}:analysis",
                    source_type="analysis",
                    segment_index=None,
                    segment_count=0,
                    start=None,
                    end=None,
                    text=analysis_text,
                    document=f"{prefix}\n关键观点：{analysis_text}",
                )
            )
        if not specs:
            raise ValueError(f"Video {video_id} has no indexable semantic content")
        return specs

    def _fingerprint(self, row: dict[str, Any]) -> str:
        payload = {
            "model": self.settings.semantic_model,
            "chunkMaxChars": self.settings.semantic_chunk_max_chars,
            "chunkMaxSegments": self.settings.semantic_chunk_max_segments,
            "videoId": int(row["id"]),
            "description": row.get("description"),
            "transcriptUpdatedAt": row.get("transcript_updated_at"),
            "analysisUpdatedAt": row.get("analysis_updated_at"),
            "segments": row.get("segments_json"),
            "summary": row.get("summary"),
            "tags": row.get("tags_json"),
            "keyPoints": row.get("key_points_json"),
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @classmethod
    def _keyword_score(cls, query: str, chunk: StoredChunk) -> float:
        needle = cls._normalize(query)
        if not needle:
            return 0.0
        haystack = cls._normalize(
            " ".join(
                filter(
                    None,
                    [chunk.title, chunk.summary or "", " ".join(chunk.tags), chunk.text],
                )
            )
        )
        if needle in haystack:
            return 1.0
        query_grams = cls._ngrams(needle)
        haystack_grams = cls._ngrams(haystack)
        if not query_grams:
            return 0.0
        return min(1.0, len(query_grams & haystack_grams) / len(query_grams))

    @staticmethod
    def _dot(left: tuple[float, ...], right: tuple[float, ...]) -> float:
        if len(left) != len(right):
            raise ValueError("Semantic query and stored vectors have different dimensions")
        return math.fsum(a * b for a, b in zip(left, right, strict=True))

    @staticmethod
    def _normalize(value: str) -> str:
        return _NORMALIZE_PATTERN.sub("", value.casefold())

    @staticmethod
    def _ngrams(value: str, size: int = 2) -> set[str]:
        if not value:
            return set()
        if len(value) <= size:
            return {value}
        return {value[index : index + size] for index in range(len(value) - size + 1)}

    @staticmethod
    def _join_text(parts: list[str]) -> str:
        return "\n".join(part.strip() for part in parts if part and part.strip())
