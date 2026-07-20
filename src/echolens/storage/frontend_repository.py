"""Read-only MySQL queries used by the frontend HTTP API."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mysql.connector import MySQLConnection
else:
    MySQLConnection = Any


class FrontendRepository:
    """Provide compact query results for browser-facing endpoints."""

    _VIDEO_SUMMARY_SELECT = """
        SELECT
            v.id,
            v.platform,
            v.video_id,
            v.creator_sec_uid,
            c.creator_name,
            v.description,
            v.source_create_time,
            v.status,
            v.updated_at,
            a.summary,
            a.tags_json,
            a.key_points_json
        FROM videos AS v
        INNER JOIN creators AS c ON c.id = v.creator_id
        LEFT JOIN analyses AS a ON a.video_id = v.id
    """

    def __init__(self, connection: MySQLConnection) -> None:
        self.connection = connection

    def dashboard_counts(self) -> dict[str, Any]:
        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM creators) AS creator_count,
                (SELECT COUNT(*) FROM videos) AS video_count,
                (SELECT COUNT(*) FROM videos WHERE status = 'done') AS completed_count
            """
        )
        row = cursor.fetchone() or {}
        cursor.close()
        return row

    def status_counts(self) -> list[dict[str, Any]]:
        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT status, COUNT(*) AS item_count
            FROM videos
            GROUP BY status
            ORDER BY status
            """
        )
        rows = cursor.fetchall()
        cursor.close()
        return rows

    def recent_videos(self, limit: int = 10) -> list[dict[str, Any]]:
        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(
            self._VIDEO_SUMMARY_SELECT
            + """
              ORDER BY COALESCE(v.source_create_time, 0) DESC, v.id DESC
              LIMIT %s
            """,
            (limit,),
        )
        rows = cursor.fetchall()
        cursor.close()
        return rows

    def completed_tag_rows(self, creator_sec_uid: str | None = None) -> list[dict[str, Any]]:
        conditions = ["v.status = 'done'", "a.tags_json IS NOT NULL"]
        params: list[Any] = []
        if creator_sec_uid:
            conditions.append("v.creator_sec_uid = %s")
            params.append(creator_sec_uid)

        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT v.creator_sec_uid, a.tags_json
            FROM videos AS v
            INNER JOIN analyses AS a ON a.video_id = v.id
            WHERE
            """
            + " AND ".join(conditions),
            tuple(params),
        )
        rows = cursor.fetchall()
        cursor.close()
        return rows

    def list_creators(
        self,
        *,
        query: str | None = None,
        limit: int = 100,
    ) -> tuple[list[dict[str, Any]], int]:
        conditions: list[str] = []
        params: list[Any] = []
        if query:
            pattern = f"%{query}%"
            conditions.append("(COALESCE(c.creator_name, '') LIKE %s OR c.sec_uid LIKE %s)")
            params.extend([pattern, pattern])
        where_sql = " WHERE " + " AND ".join(conditions) if conditions else ""

        cursor = self.connection.cursor(dictionary=True)
        cursor.execute("SELECT COUNT(*) AS total FROM creators AS c" + where_sql, tuple(params))
        total_row = cursor.fetchone() or {}
        total = int(total_row.get("total") or 0)

        cursor.execute(
            """
            SELECT
                c.platform,
                c.sec_uid,
                c.creator_name,
                COUNT(v.id) AS video_count,
                SUM(CASE WHEN v.status = 'done' THEN 1 ELSE 0 END) AS completed_count,
                MAX(v.updated_at) AS updated_at
            FROM creators AS c
            LEFT JOIN videos AS v ON v.creator_id = c.id
            """
            + where_sql
            + """
            GROUP BY c.id, c.platform, c.sec_uid, c.creator_name
            ORDER BY completed_count DESC, video_count DESC, c.id
            LIMIT %s
            """,
            tuple([*params, limit]),
        )
        rows = cursor.fetchall()
        cursor.close()
        return rows, total

    def get_creator(self, sec_uid: str) -> dict[str, Any] | None:
        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                c.platform,
                c.sec_uid,
                c.creator_name,
                COUNT(v.id) AS video_count,
                SUM(CASE WHEN v.status = 'done' THEN 1 ELSE 0 END) AS completed_count,
                MAX(v.updated_at) AS updated_at
            FROM creators AS c
            LEFT JOIN videos AS v ON v.creator_id = c.id
            WHERE c.sec_uid = %s
            GROUP BY c.id, c.platform, c.sec_uid, c.creator_name
            LIMIT 1
            """,
            (sec_uid,),
        )
        row = cursor.fetchone()
        cursor.close()
        return row

    def creator_videos(self, sec_uid: str, limit: int = 100) -> list[dict[str, Any]]:
        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(
            self._VIDEO_SUMMARY_SELECT
            + """
              WHERE v.creator_sec_uid = %s
              ORDER BY COALESCE(v.source_create_time, 0) DESC, v.id DESC
              LIMIT %s
            """,
            (sec_uid, limit),
        )
        rows = cursor.fetchall()
        cursor.close()
        return rows

    def search_videos(
        self,
        *,
        query: str,
        creator_sec_uid: str | None = None,
        tag: str | None = None,
        limit: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        pattern = f"%{query}%"
        conditions = [
            "v.status = 'done'",
            """
            (
                COALESCE(v.description, '') LIKE %s
                OR COALESCE(a.summary, '') LIKE %s
                OR COALESCE(t.transcript_text, '') LIKE %s
                OR CAST(a.tags_json AS CHAR) LIKE %s
                OR CAST(a.key_points_json AS CHAR) LIKE %s
            )
            """,
        ]
        params: list[Any] = [pattern] * 5
        if creator_sec_uid:
            conditions.append("v.creator_sec_uid = %s")
            params.append(creator_sec_uid)
        if tag:
            conditions.append("JSON_CONTAINS(a.tags_json, JSON_QUOTE(%s))")
            params.append(tag)

        from_sql = """
            FROM videos AS v
            INNER JOIN creators AS c ON c.id = v.creator_id
            INNER JOIN transcripts AS t ON t.video_id = v.id
            INNER JOIN analyses AS a ON a.video_id = v.id
            WHERE
        """ + " AND ".join(conditions)

        cursor = self.connection.cursor(dictionary=True)
        cursor.execute("SELECT COUNT(*) AS total " + from_sql, tuple(params))
        total_row = cursor.fetchone() or {}
        total = int(total_row.get("total") or 0)

        cursor.execute(
            """
            SELECT
                v.id,
                v.platform,
                v.video_id,
                v.creator_sec_uid,
                c.creator_name,
                v.description,
                v.source_create_time,
                v.status,
                v.updated_at,
                t.transcript_text,
                t.segments_json,
                a.summary,
                a.tags_json,
                a.key_points_json
            """
            + from_sql
            + """
              ORDER BY COALESCE(v.source_create_time, 0) DESC, v.id DESC
              LIMIT %s
            """,
            tuple([*params, limit]),
        )
        rows = cursor.fetchall()
        cursor.close()
        return rows, total

    def get_video(self, video_db_id: int) -> dict[str, Any] | None:
        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                v.id,
                v.platform,
                v.video_id,
                v.creator_sec_uid,
                c.creator_name,
                v.description,
                v.source_create_time,
                v.status,
                v.updated_at,
                v.audio_path,
                v.audio_size,
                t.transcript_text,
                t.segments_json,
                t.language,
                t.model_name AS transcription_model,
                a.summary,
                a.tags_json,
                a.key_points_json,
                a.model_name AS analysis_model
            FROM videos AS v
            INNER JOIN creators AS c ON c.id = v.creator_id
            LEFT JOIN transcripts AS t ON t.video_id = v.id
            LEFT JOIN analyses AS a ON a.video_id = v.id
            WHERE v.id = %s
            LIMIT 1
            """,
            (video_db_id,),
        )
        row = cursor.fetchone()
        cursor.close()
        return row

    def get_audio_path(self, video_db_id: int) -> str | None:
        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT audio_path
            FROM videos
            WHERE id = %s AND audio_path IS NOT NULL
            LIMIT 1
            """,
            (video_db_id,),
        )
        row = cursor.fetchone()
        cursor.close()
        if row is None:
            return None
        value = row.get("audio_path")
        return str(value) if value else None
