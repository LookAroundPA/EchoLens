"""MySQL reads used to build the local semantic knowledge index."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mysql.connector import MySQLConnection
else:
    MySQLConnection = Any


class SemanticSourceRepository:
    """Read completed videos together with transcript and analysis revisions."""

    _SELECT = """
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
            t.updated_at AS transcript_updated_at,
            a.summary,
            a.tags_json,
            a.key_points_json,
            a.updated_at AS analysis_updated_at
        FROM videos AS v
        INNER JOIN creators AS c ON c.id = v.creator_id
        INNER JOIN transcripts AS t ON t.video_id = v.id
        INNER JOIN analyses AS a ON a.video_id = v.id
    """

    def __init__(self, connection: MySQLConnection) -> None:
        self.connection = connection

    def list_indexable_videos(self) -> list[dict[str, Any]]:
        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(
            self._SELECT
            + """
              WHERE v.status = 'done'
                AND t.segments_json IS NOT NULL
              ORDER BY v.id
            """
        )
        rows = cursor.fetchall()
        cursor.close()
        return rows

    def get_indexable_video(self, video_db_id: int) -> dict[str, Any] | None:
        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(
            self._SELECT
            + """
              WHERE v.id = %s
                AND v.status = 'done'
                AND t.segments_json IS NOT NULL
              LIMIT 1
            """,
            (video_db_id,),
        )
        row = cursor.fetchone()
        cursor.close()
        return row
