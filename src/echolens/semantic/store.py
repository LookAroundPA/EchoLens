"""Persistent SQLite store for lightweight local semantic vectors."""

from __future__ import annotations

from array import array
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Iterable


@dataclass(frozen=True)
class StoredChunk:
    chunk_id: str
    video_id: int
    platform: str
    platform_video_id: str
    creator_sec_uid: str
    creator_name: str | None
    title: str
    summary: str | None
    tags: tuple[str, ...]
    published_at: str | None
    source_type: str
    segment_index: int | None
    segment_count: int
    start: float | None
    end: float | None
    text: str
    vector: tuple[float, ...]


@dataclass(frozen=True)
class SemanticStoreStatus:
    ready: bool
    model: str | None
    video_count: int
    chunk_count: int
    indexed_at: str | None


class SemanticStore:
    """Store normalized float vectors and source metadata in one local SQLite file."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS semantic_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS semantic_videos (
                    video_id INTEGER PRIMARY KEY,
                    fingerprint TEXT NOT NULL,
                    chunk_count INTEGER NOT NULL,
                    indexed_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS semantic_chunks (
                    chunk_id TEXT PRIMARY KEY,
                    video_id INTEGER NOT NULL,
                    platform TEXT NOT NULL,
                    platform_video_id TEXT NOT NULL,
                    creator_sec_uid TEXT NOT NULL,
                    creator_name TEXT NULL,
                    title TEXT NOT NULL,
                    summary TEXT NULL,
                    tags_json TEXT NOT NULL,
                    published_at TEXT NULL,
                    source_type TEXT NOT NULL,
                    segment_index INTEGER NULL,
                    segment_count INTEGER NOT NULL,
                    start REAL NULL,
                    end REAL NULL,
                    text TEXT NOT NULL,
                    vector BLOB NOT NULL,
                    vector_dim INTEGER NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_semantic_chunks_video
                    ON semantic_chunks(video_id);
                CREATE INDEX IF NOT EXISTS idx_semantic_chunks_creator
                    ON semantic_chunks(creator_sec_uid);
                """
            )

    def clear(self) -> None:
        self.initialize()
        with self._connect() as connection:
            connection.execute("DELETE FROM semantic_chunks")
            connection.execute("DELETE FROM semantic_videos")
            connection.execute("DELETE FROM semantic_meta")

    def status(self) -> SemanticStoreStatus:
        if not self.path.is_file():
            return SemanticStoreStatus(False, None, 0, 0, None)
        self.initialize()
        with self._connect() as connection:
            video_count = int(
                connection.execute("SELECT COUNT(*) FROM semantic_videos").fetchone()[0]
            )
            chunk_count = int(
                connection.execute("SELECT COUNT(*) FROM semantic_chunks").fetchone()[0]
            )
            meta = dict(connection.execute("SELECT key, value FROM semantic_meta").fetchall())
        return SemanticStoreStatus(
            ready=chunk_count > 0,
            model=meta.get("model"),
            video_count=video_count,
            chunk_count=chunk_count,
            indexed_at=meta.get("indexed_at"),
        )

    def fingerprints(self) -> dict[int, str]:
        self.initialize()
        with self._connect() as connection:
            return {
                int(row[0]): str(row[1])
                for row in connection.execute(
                    "SELECT video_id, fingerprint FROM semantic_videos"
                ).fetchall()
            }

    def replace_video(
        self,
        *,
        video_id: int,
        fingerprint: str,
        chunks: Iterable[StoredChunk],
        model: str,
    ) -> int:
        self.initialize()
        materialized = list(chunks)
        indexed_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute("DELETE FROM semantic_chunks WHERE video_id = ?", (video_id,))
            connection.executemany(
                """
                INSERT INTO semantic_chunks (
                    chunk_id, video_id, platform, platform_video_id,
                    creator_sec_uid, creator_name, title, summary, tags_json,
                    published_at, source_type, segment_index, segment_count,
                    start, end, text, vector, vector_dim
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item.chunk_id,
                        item.video_id,
                        item.platform,
                        item.platform_video_id,
                        item.creator_sec_uid,
                        item.creator_name,
                        item.title,
                        item.summary,
                        json.dumps(item.tags, ensure_ascii=False),
                        item.published_at,
                        item.source_type,
                        item.segment_index,
                        item.segment_count,
                        item.start,
                        item.end,
                        item.text,
                        self._pack_vector(item.vector),
                        len(item.vector),
                    )
                    for item in materialized
                ],
            )
            connection.execute(
                """
                INSERT INTO semantic_videos (video_id, fingerprint, chunk_count, indexed_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(video_id) DO UPDATE SET
                    fingerprint = excluded.fingerprint,
                    chunk_count = excluded.chunk_count,
                    indexed_at = excluded.indexed_at
                """,
                (video_id, fingerprint, len(materialized), indexed_at),
            )
            self._set_meta(connection, "model", model)
            self._set_meta(connection, "indexed_at", indexed_at)
        return len(materialized)

    def remove_video(self, video_id: int) -> None:
        self.initialize()
        with self._connect() as connection:
            connection.execute("DELETE FROM semantic_chunks WHERE video_id = ?", (video_id,))
            connection.execute("DELETE FROM semantic_videos WHERE video_id = ?", (video_id,))

    def remove_missing_videos(self, current_video_ids: set[int]) -> int:
        self.initialize()
        with self._connect() as connection:
            existing = {
                int(row[0])
                for row in connection.execute("SELECT video_id FROM semantic_videos").fetchall()
            }
            stale = sorted(existing - current_video_ids)
            if stale:
                placeholders = ",".join("?" for _ in stale)
                connection.execute(
                    f"DELETE FROM semantic_chunks WHERE video_id IN ({placeholders})",
                    tuple(stale),
                )
                connection.execute(
                    f"DELETE FROM semantic_videos WHERE video_id IN ({placeholders})",
                    tuple(stale),
                )
        return len(stale)

    def candidates(self, creator_sec_uid: str | None = None) -> list[StoredChunk]:
        self.initialize()
        sql = "SELECT * FROM semantic_chunks"
        params: tuple[object, ...] = ()
        if creator_sec_uid:
            sql += " WHERE creator_sec_uid = ?"
            params = (creator_sec_uid,)
        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self._row_to_chunk(row) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        connection.execute("PRAGMA busy_timeout=30000")
        return connection

    @staticmethod
    def _pack_vector(vector: tuple[float, ...]) -> bytes:
        return array("f", vector).tobytes()

    @staticmethod
    def _unpack_vector(payload: bytes, dimension: int) -> tuple[float, ...]:
        values = array("f")
        values.frombytes(payload)
        if len(values) != dimension:
            raise ValueError("Stored semantic vector dimension is invalid")
        return tuple(float(value) for value in values)

    @staticmethod
    def _set_meta(connection: sqlite3.Connection, key: str, value: str) -> None:
        connection.execute(
            """
            INSERT INTO semantic_meta (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )

    def _row_to_chunk(self, row: sqlite3.Row) -> StoredChunk:
        raw_tags = json.loads(str(row["tags_json"]))
        return StoredChunk(
            chunk_id=str(row["chunk_id"]),
            video_id=int(row["video_id"]),
            platform=str(row["platform"]),
            platform_video_id=str(row["platform_video_id"]),
            creator_sec_uid=str(row["creator_sec_uid"]),
            creator_name=(str(row["creator_name"]) if row["creator_name"] is not None else None),
            title=str(row["title"]),
            summary=(str(row["summary"]) if row["summary"] is not None else None),
            tags=tuple(str(item) for item in raw_tags if str(item).strip()),
            published_at=(str(row["published_at"]) if row["published_at"] is not None else None),
            source_type=str(row["source_type"]),
            segment_index=(int(row["segment_index"]) if row["segment_index"] is not None else None),
            segment_count=int(row["segment_count"]),
            start=(float(row["start"]) if row["start"] is not None else None),
            end=(float(row["end"]) if row["end"] is not None else None),
            text=str(row["text"]),
            vector=self._unpack_vector(bytes(row["vector"]), int(row["vector_dim"])),
        )
