"""Transactional topic-review, alias, and merge maintenance operations."""

from __future__ import annotations

from datetime import datetime
import json
from typing import TYPE_CHECKING, Any

from echolens.intelligence.normalization import normalize_topic_name
from echolens.intelligence.repository import IntelligenceRepository

if TYPE_CHECKING:
    from mysql.connector import MySQLConnection
else:
    MySQLConnection = Any


class IntelligenceManagementRepository:
    """Maintain the controlled topic catalog without losing opinion evidence."""

    def __init__(self, connection: MySQLConnection) -> None:
        self.connection = connection

    def list_topics(
        self,
        *,
        status: str = "all",
        topic_type: str | None = None,
        query: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        conditions = ["t.status <> 'archived'"]
        params: list[Any] = []
        if status != "all":
            conditions.append("t.status = %s")
            params.append(status)
        if topic_type is not None:
            conditions.append("t.topic_type = %s")
            params.append(topic_type)
        if query:
            conditions.append(
                "(t.canonical_name LIKE %s OR EXISTS ("
                "SELECT 1 FROM topic_aliases AS search_alias "
                "WHERE search_alias.topic_id = t.id AND search_alias.alias LIKE %s))"
            )
            pattern = f"%{query.strip()}%"
            params.extend([pattern, pattern])

        where_sql = " AND ".join(conditions)
        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT COUNT(*) AS item_count FROM topics AS t WHERE " + where_sql,
            tuple(params),
        )
        total = int((cursor.fetchone() or {}).get("item_count") or 0)
        cursor.execute(
            """
            SELECT
                t.id,
                t.canonical_name,
                t.topic_type,
                t.status,
                t.created_at,
                t.updated_at,
                COUNT(DISTINCT o.id) AS opinion_count,
                COUNT(DISTINCT o.creator_id) AS creator_count,
                MAX(o.published_at) AS latest_published_at
            FROM topics AS t
            LEFT JOIN creator_topic_opinions AS o ON o.topic_id = t.id
            WHERE
            """
            + where_sql
            + " GROUP BY t.id, t.canonical_name, t.topic_type, t.status, t.created_at, t.updated_at "
            + "ORDER BY CASE WHEN t.status = 'pending' THEN 0 ELSE 1 END, "
            + "opinion_count DESC, latest_published_at DESC, t.id DESC LIMIT %s OFFSET %s",
            tuple([*params, limit, offset]),
        )
        rows = list(cursor.fetchall())
        cursor.close()
        for row in rows:
            row["aliases"] = self.list_aliases(int(row["id"]))
        return rows, total

    def get_topic_item(self, topic_id: int) -> dict[str, Any] | None:
        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                t.id,
                t.canonical_name,
                t.topic_type,
                t.status,
                t.created_at,
                t.updated_at,
                COUNT(DISTINCT o.id) AS opinion_count,
                COUNT(DISTINCT o.creator_id) AS creator_count,
                MAX(o.published_at) AS latest_published_at
            FROM topics AS t
            LEFT JOIN creator_topic_opinions AS o ON o.topic_id = t.id
            WHERE t.id = %s AND t.status <> 'archived'
            GROUP BY t.id, t.canonical_name, t.topic_type, t.status, t.created_at, t.updated_at
            LIMIT 1
            """,
            (topic_id,),
        )
        row = cursor.fetchone()
        cursor.close()
        if row is not None:
            row["aliases"] = self.list_aliases(topic_id)
        return row

    def list_aliases(self, topic_id: int) -> list[str]:
        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT alias
            FROM topic_aliases
            WHERE topic_id = %s
            ORDER BY CASE WHEN source = 'manual' THEN 0 WHEN source = 'seed' THEN 1 ELSE 2 END, id
            """,
            (topic_id,),
        )
        aliases = [str(row["alias"]) for row in cursor.fetchall()]
        cursor.close()
        return aliases

    def update_topic(self, topic_id: int, *, canonical_name: str, status: str) -> None:
        normalized = normalize_topic_name(canonical_name)
        if not normalized:
            raise ValueError("Topic name cannot be empty")
        cursor = self.connection.cursor(dictionary=True)
        try:
            topic = self._topic_for_update(cursor, topic_id)
            self._ensure_name_available(
                cursor,
                topic_id=topic_id,
                topic_type=str(topic["topic_type"]),
                normalized_name=normalized,
            )
            now = datetime.now()
            cursor.execute(
                """
                UPDATE topics
                SET canonical_name = %s,
                    normalized_name = %s,
                    status = %s,
                    updated_at = %s
                WHERE id = %s
                """,
                (canonical_name.strip(), normalized, status, now, topic_id),
            )
            self._insert_alias(
                cursor,
                topic_id=topic_id,
                alias=canonical_name,
                normalized_alias=normalized,
                source="manual",
            )
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise
        finally:
            cursor.close()

    def add_alias(self, topic_id: int, alias: str) -> None:
        normalized = normalize_topic_name(alias)
        if not normalized:
            raise ValueError("Alias cannot be empty")
        cursor = self.connection.cursor(dictionary=True)
        try:
            topic = self._topic_for_update(cursor, topic_id)
            cursor.execute(
                """
                SELECT t.id, t.canonical_name
                FROM topics AS t
                WHERE t.topic_type = %s
                  AND t.status <> 'archived'
                  AND t.id <> %s
                  AND (
                      t.normalized_name = %s
                      OR EXISTS (
                          SELECT 1
                          FROM topic_aliases AS ta
                          WHERE ta.topic_id = t.id
                            AND ta.normalized_alias = %s
                      )
                  )
                LIMIT 1
                """,
                (topic["topic_type"], topic_id, normalized, normalized),
            )
            conflict = cursor.fetchone()
            if conflict is not None:
                raise ValueError(
                    f"Alias already belongs to topic {conflict['canonical_name']} ({conflict['id']}); merge topics instead"
                )
            self._insert_alias(
                cursor,
                topic_id=topic_id,
                alias=alias,
                normalized_alias=normalized,
                source="manual",
            )
            cursor.execute(
                "UPDATE topics SET updated_at = %s WHERE id = %s",
                (datetime.now(), topic_id),
            )
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise
        finally:
            cursor.close()

    def merge_topics(self, source_topic_id: int, target_topic_id: int) -> int:
        if source_topic_id == target_topic_id:
            raise ValueError("Source and target topics must be different")
        cursor = self.connection.cursor(dictionary=True)
        try:
            source = self._topic_for_update(cursor, source_topic_id)
            target = self._topic_for_update(cursor, target_topic_id)
            if str(source["topic_type"]) != str(target["topic_type"]):
                raise ValueError("Only topics of the same type can be merged")
            if str(target["status"]) != "active":
                raise ValueError("Merge target must be an active reviewed topic")

            cursor.execute(
                """
                SELECT DISTINCT creator_id
                FROM creator_topic_opinions
                WHERE topic_id IN (%s, %s)
                """,
                (source_topic_id, target_topic_id),
            )
            creator_ids = [int(row["creator_id"]) for row in cursor.fetchall()]

            cursor.execute(
                """
                SELECT alias, normalized_alias, source
                FROM topic_aliases
                WHERE topic_id = %s
                """,
                (source_topic_id,),
            )
            source_aliases = list(cursor.fetchall())
            source_aliases.append(
                {
                    "alias": source["canonical_name"],
                    "normalized_alias": source["normalized_name"],
                    "source": "manual",
                }
            )
            for item in source_aliases:
                self._ensure_merge_alias_available(
                    cursor,
                    topic_type=str(source["topic_type"]),
                    normalized_alias=str(item["normalized_alias"]),
                    source_topic_id=source_topic_id,
                    target_topic_id=target_topic_id,
                )
                self._insert_alias(
                    cursor,
                    topic_id=target_topic_id,
                    alias=str(item["alias"]),
                    normalized_alias=str(item["normalized_alias"]),
                    source="manual" if str(item["source"]) == "manual" else "observed",
                )

            cursor.execute(
                "UPDATE creator_topic_opinions SET topic_id = %s, updated_at = %s WHERE topic_id = %s",
                (target_topic_id, datetime.now(), source_topic_id),
            )
            moved = int(cursor.rowcount)
            cursor.execute(
                """
                INSERT INTO topic_merge_history (
                    source_topic_id,
                    target_topic_id,
                    source_name,
                    target_name,
                    source_aliases_json,
                    moved_opinion_count,
                    merged_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    source_topic_id,
                    target_topic_id,
                    source["canonical_name"],
                    target["canonical_name"],
                    json.dumps(
                        list(dict.fromkeys(str(item["alias"]) for item in source_aliases)),
                        ensure_ascii=False,
                    ),
                    moved,
                    datetime.now(),
                ),
            )
            cursor.execute(
                "DELETE FROM opinion_changes WHERE topic_id IN (%s, %s)",
                (source_topic_id, target_topic_id),
            )
            cursor.execute("DELETE FROM topic_aliases WHERE topic_id = %s", (source_topic_id,))
            cursor.execute(
                "UPDATE topics SET status = 'archived', updated_at = %s WHERE id = %s",
                (datetime.now(), source_topic_id),
            )
            cursor.execute(
                "UPDATE topics SET updated_at = %s WHERE id = %s",
                (datetime.now(), target_topic_id),
            )

            intelligence = IntelligenceRepository(self.connection)
            for creator_id in creator_ids:
                intelligence.rebuild_change_history(creator_id, target_topic_id)
            self.connection.commit()
            return moved
        except Exception:
            self.connection.rollback()
            raise
        finally:
            cursor.close()

    @staticmethod
    def _ensure_merge_alias_available(
        cursor: Any,
        *,
        topic_type: str,
        normalized_alias: str,
        source_topic_id: int,
        target_topic_id: int,
    ) -> None:
        cursor.execute(
            """
            SELECT t.id, t.canonical_name
            FROM topics AS t
            WHERE t.topic_type = %s
              AND t.status <> 'archived'
              AND t.id NOT IN (%s, %s)
              AND (
                  t.normalized_name = %s
                  OR EXISTS (
                      SELECT 1
                      FROM topic_aliases AS ta
                      WHERE ta.topic_id = t.id
                        AND ta.normalized_alias = %s
                  )
              )
            LIMIT 1
            """,
            (
                topic_type,
                source_topic_id,
                target_topic_id,
                normalized_alias,
                normalized_alias,
            ),
        )
        conflict = cursor.fetchone()
        if conflict is not None:
            raise ValueError(
                f"Source alias conflicts with topic {conflict['canonical_name']} ({conflict['id']})"
            )

    @staticmethod
    def _insert_alias(
        cursor: Any,
        *,
        topic_id: int,
        alias: str,
        normalized_alias: str,
        source: str,
    ) -> None:
        cursor.execute(
            """
            INSERT INTO topic_aliases (topic_id, alias, normalized_alias, source, created_at)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                alias = VALUES(alias),
                source = CASE
                    WHEN topic_aliases.source = 'manual' THEN topic_aliases.source
                    ELSE VALUES(source)
                END
            """,
            (topic_id, alias.strip(), normalized_alias, source, datetime.now()),
        )

    @staticmethod
    def _topic_for_update(cursor: Any, topic_id: int) -> dict[str, Any]:
        cursor.execute(
            """
            SELECT id, canonical_name, normalized_name, topic_type, status
            FROM topics
            WHERE id = %s AND status <> 'archived'
            LIMIT 1 FOR UPDATE
            """,
            (topic_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise KeyError(f"Topic {topic_id} does not exist")
        return row

    @staticmethod
    def _ensure_name_available(
        cursor: Any,
        *,
        topic_id: int,
        topic_type: str,
        normalized_name: str,
    ) -> None:
        cursor.execute(
            """
            SELECT t.id, t.canonical_name
            FROM topics AS t
            WHERE t.topic_type = %s
              AND t.status <> 'archived'
              AND t.id <> %s
              AND (
                  t.normalized_name = %s
                  OR EXISTS (
                      SELECT 1
                      FROM topic_aliases AS ta
                      WHERE ta.topic_id = t.id
                        AND ta.normalized_alias = %s
                  )
              )
            LIMIT 1
            """,
            (topic_type, topic_id, normalized_name, normalized_name),
        )
        conflict = cursor.fetchone()
        if conflict is not None:
            raise ValueError(
                f"Topic name already exists as {conflict['canonical_name']} ({conflict['id']}); merge topics instead"
            )
