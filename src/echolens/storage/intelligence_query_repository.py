"""Read models for topic history and market-radar aggregation."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mysql.connector import MySQLConnection
else:
    MySQLConnection = Any


class IntelligenceQueryRepository:
    """Query normalized opinions without exposing SQL to the API layer."""

    def __init__(self, connection: MySQLConnection) -> None:
        self.connection = connection

    def get_topic(self, topic_id: int) -> dict[str, Any] | None:
        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, canonical_name, topic_type, status, created_at, updated_at
            FROM topics
            WHERE id = %s
              AND status <> 'archived'
            LIMIT 1
            """,
            (topic_id,),
        )
        row = cursor.fetchone()
        cursor.close()
        return row

    def list_aliases(self, topic_id: int) -> list[str]:
        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT alias
            FROM topic_aliases
            WHERE topic_id = %s
            ORDER BY CASE WHEN source = 'manual' THEN 0 WHEN source = 'seed' THEN 1 ELSE 2 END,
                     id
            """,
            (topic_id,),
        )
        aliases = [str(row["alias"]) for row in cursor.fetchall()]
        cursor.close()
        return aliases

    def list_opinions_between(
        self,
        start: datetime,
        end: datetime,
        *,
        topic_status: str = "all",
        topic_type: str | None = None,
        topic_id: int | None = None,
    ) -> list[dict[str, Any]]:
        conditions = ["o.published_at >= %s", "o.published_at < %s", "t.status <> 'archived'"]
        params: list[Any] = [start, end]
        if topic_status != "all":
            conditions.append("t.status = %s")
            params.append(topic_status)
        if topic_type is not None:
            conditions.append("t.topic_type = %s")
            params.append(topic_type)
        if topic_id is not None:
            conditions.append("t.id = %s")
            params.append(topic_id)

        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                o.id,
                o.topic_id,
                o.creator_id,
                o.stance,
                o.source_type,
                o.published_at,
                t.canonical_name,
                t.topic_type,
                t.status AS topic_status
            FROM creator_topic_opinions AS o
            INNER JOIN topics AS t ON t.id = o.topic_id
            WHERE
            """
            + " AND ".join(conditions)
            + " ORDER BY o.published_at, o.id",
            tuple(params),
        )
        rows = list(cursor.fetchall())
        cursor.close()
        return rows

    def list_changes_between(
        self,
        start: datetime,
        end: datetime,
        *,
        topic_status: str = "all",
        topic_type: str | None = None,
        topic_id: int | None = None,
    ) -> list[dict[str, Any]]:
        conditions = ["oc.detected_at >= %s", "oc.detected_at < %s", "t.status <> 'archived'"]
        params: list[Any] = [start, end]
        if topic_status != "all":
            conditions.append("t.status = %s")
            params.append(topic_status)
        if topic_type is not None:
            conditions.append("t.topic_type = %s")
            params.append(topic_type)
        if topic_id is not None:
            conditions.append("t.id = %s")
            params.append(topic_id)

        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT oc.id, oc.topic_id, oc.creator_id, oc.change_type, oc.detected_at
            FROM opinion_changes AS oc
            INNER JOIN topics AS t ON t.id = oc.topic_id
            WHERE
            """
            + " AND ".join(conditions)
            + " ORDER BY oc.detected_at, oc.id",
            tuple(params),
        )
        rows = list(cursor.fetchall())
        cursor.close()
        return rows

    def list_topic_opinions(
        self,
        topic_id: int,
        *,
        creator_sec_uid: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        conditions = ["o.topic_id = %s"]
        params: list[Any] = [topic_id]
        if creator_sec_uid is not None:
            conditions.append("c.sec_uid = %s")
            params.append(creator_sec_uid)

        where_sql = " AND ".join(conditions)
        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT COUNT(*) AS item_count
            FROM creator_topic_opinions AS o
            INNER JOIN creators AS c ON c.id = o.creator_id
            WHERE
            """
            + where_sql,
            tuple(params),
        )
        total_row = cursor.fetchone() or {}
        total = int(total_row.get("item_count") or 0)

        cursor.execute(
            """
            SELECT
                o.id,
                o.topic_id,
                o.creator_id,
                c.platform AS creator_platform,
                c.sec_uid AS creator_sec_uid,
                c.creator_name,
                o.video_id,
                v.video_id AS platform_video_id,
                v.description AS video_description,
                o.raw_subject,
                o.stance,
                o.source_type,
                o.time_horizon,
                o.confidence,
                o.conclusion,
                o.reasoning_json,
                o.risks_json,
                o.evidence_quote,
                o.published_at,
                oc.change_type,
                oc.change_summary
            FROM creator_topic_opinions AS o
            INNER JOIN creators AS c ON c.id = o.creator_id
            INNER JOIN videos AS v ON v.id = o.video_id
            LEFT JOIN opinion_changes AS oc ON oc.current_opinion_id = o.id
            WHERE
            """
            + where_sql
            + " ORDER BY o.published_at DESC, o.id DESC LIMIT %s OFFSET %s",
            tuple([*params, limit, offset]),
        )
        rows = list(cursor.fetchall())
        cursor.close()
        return rows, total

    def list_topic_assets(self, topic_id: int) -> list[dict[str, Any]]:
        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                tam.id,
                tam.topic_id,
                tam.relation_type,
                tam.note,
                tam.source,
                tam.created_at,
                tam.updated_at,
                ra.id AS asset_id,
                ra.asset_type,
                ra.code,
                ra.name,
                ra.market,
                ra.status AS asset_status
            FROM topic_asset_mappings AS tam
            INNER JOIN reference_assets AS ra ON ra.id = tam.asset_id
            WHERE tam.topic_id = %s
              AND ra.status = 'active'
            ORDER BY
                CASE tam.relation_type
                    WHEN 'direct' THEN 0
                    WHEN 'benchmark' THEN 1
                    WHEN 'upstream' THEN 2
                    WHEN 'downstream' THEN 3
                    ELSE 4
                END,
                ra.asset_type,
                ra.code
            """,
            (topic_id,),
        )
        rows = list(cursor.fetchall())
        cursor.close()
        return rows

    def list_topic_changes(self, topic_id: int, *, limit: int = 50) -> list[dict[str, Any]]:
        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                oc.id,
                oc.topic_id,
                oc.creator_id,
                c.platform AS creator_platform,
                c.sec_uid AS creator_sec_uid,
                c.creator_name,
                oc.current_opinion_id,
                current_opinion.video_id AS current_video_id,
                oc.change_type,
                oc.previous_stance,
                oc.current_stance,
                oc.change_summary,
                oc.detected_at
            FROM opinion_changes AS oc
            INNER JOIN creators AS c ON c.id = oc.creator_id
            INNER JOIN creator_topic_opinions AS current_opinion
                ON current_opinion.id = oc.current_opinion_id
            WHERE oc.topic_id = %s
            ORDER BY oc.detected_at DESC, oc.id DESC
            LIMIT %s
            """,
            (topic_id, limit),
        )
        rows = list(cursor.fetchall())
        cursor.close()
        return rows
