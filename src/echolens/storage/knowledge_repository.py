"""Read-only MySQL queries over completed EchoLens knowledge."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mysql.connector import MySQLConnection
else:
    MySQLConnection = Any

from echolens.knowledge.models import CreatorKnowledgeSummary, KnowledgeItem


class KnowledgeRepository:
    """Query creators, completed analyses, transcripts, and source metadata."""

    _ITEM_SELECT = """
        SELECT
            v.id AS db_id,
            v.platform,
            v.video_id,
            v.creator_sec_uid,
            c.creator_name,
            v.description,
            v.source_create_time,
            v.status,
            a.summary,
            a.tags_json,
            a.key_points_json,
            a.model_name AS analysis_model,
            t.language,
            t.transcript_text
        FROM videos AS v
        INNER JOIN creators AS c ON c.id = v.creator_id
        INNER JOIN transcripts AS t ON t.video_id = v.id
        INNER JOIN analyses AS a ON a.video_id = v.id
    """

    def __init__(self, connection: MySQLConnection) -> None:
        self.connection = connection

    def list_creators(self, limit: int = 100) -> list[CreatorKnowledgeSummary]:
        """Return creators with video and completed-analysis counts."""

        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                c.platform,
                c.sec_uid,
                c.creator_name,
                COUNT(v.id) AS video_count,
                SUM(CASE WHEN v.status = 'done' THEN 1 ELSE 0 END) AS done_count
            FROM creators AS c
            LEFT JOIN videos AS v ON v.creator_id = c.id
            GROUP BY c.id, c.platform, c.sec_uid, c.creator_name
            ORDER BY done_count DESC, video_count DESC, c.id
            LIMIT %s
            """,
            (limit,),
        )
        rows = cursor.fetchall()
        cursor.close()
        return [CreatorKnowledgeSummary.from_row(row) for row in rows]

    def list_items(
        self,
        *,
        creator_sec_uid: str | None = None,
        tag: str | None = None,
        keyword: str | None = None,
        limit: int = 20,
    ) -> list[KnowledgeItem]:
        """List completed items with optional creator, tag, and keyword filters."""

        conditions = ["v.status = %s"]
        params: list[Any] = ["done"]

        if creator_sec_uid:
            conditions.append("v.creator_sec_uid = %s")
            params.append(creator_sec_uid)
        if tag:
            conditions.append("JSON_CONTAINS(a.tags_json, JSON_QUOTE(%s))")
            params.append(tag)
        if keyword:
            pattern = f"%{keyword}%"
            conditions.append(
                """
                (
                    COALESCE(v.description, '') LIKE %s
                    OR COALESCE(a.summary, '') LIKE %s
                    OR COALESCE(t.transcript_text, '') LIKE %s
                    OR CAST(a.tags_json AS CHAR) LIKE %s
                    OR CAST(a.key_points_json AS CHAR) LIKE %s
                )
                """
            )
            params.extend([pattern] * 5)

        sql = (
            self._ITEM_SELECT
            + " WHERE "
            + " AND ".join(conditions)
            + """
              ORDER BY COALESCE(v.source_create_time, 0) DESC, v.id DESC
              LIMIT %s
            """
        )
        params.append(limit)

        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(sql, tuple(params))
        rows = cursor.fetchall()
        cursor.close()
        return [KnowledgeItem.from_row(row) for row in rows]

    def find_video(
        self,
        video_id: str,
        creator_sec_uid: str | None = None,
    ) -> list[KnowledgeItem]:
        """Find completed knowledge by platform video id."""

        conditions = ["v.status = %s", "v.video_id = %s"]
        params: list[Any] = ["done", video_id]
        if creator_sec_uid:
            conditions.append("v.creator_sec_uid = %s")
            params.append(creator_sec_uid)

        sql = self._ITEM_SELECT + " WHERE " + " AND ".join(conditions) + " ORDER BY v.id"
        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(sql, tuple(params))
        rows = cursor.fetchall()
        cursor.close()
        return [KnowledgeItem.from_row(row) for row in rows]
