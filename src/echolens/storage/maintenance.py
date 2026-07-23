"""Small, idempotent MySQL maintenance operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mysql.connector import MySQLConnection
else:
    MySQLConnection = Any


MARKET_INSIGHTS_COLUMN = "market_insights_json"


class DatabaseMaintenance:
    """Apply narrowly scoped schema upgrades and analysis backfills."""

    def __init__(self, connection: MySQLConnection) -> None:
        self.connection = connection

    def ensure_market_insights_column(self) -> bool:
        """Add analyses.market_insights_json when it does not yet exist.

        Returns True when the schema was changed and False when it was already current.
        """

        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT COUNT(*) AS column_count
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'analyses'
              AND COLUMN_NAME = %s
            """,
            (MARKET_INSIGHTS_COLUMN,),
        )
        row = cursor.fetchone() or {}
        exists = int(row.get("column_count") or 0) > 0
        if exists:
            cursor.close()
            return False

        cursor.execute(
            """
            ALTER TABLE analyses
            ADD COLUMN market_insights_json JSON NULL AFTER key_points_json
            """
        )
        cursor.close()
        self.connection.commit()
        return True

    def count_reanalysis_candidates(self) -> int:
        """Count completed videos whose market conclusions have not been generated."""

        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT COUNT(*) AS item_count
            FROM videos AS v
            INNER JOIN transcripts AS t ON t.video_id = v.id
            LEFT JOIN analyses AS a ON a.video_id = v.id
            WHERE v.status IN ('done', 'analysis_failed')
              AND a.market_insights_json IS NULL
            """
        )
        row = cursor.fetchone() or {}
        cursor.close()
        return int(row.get("item_count") or 0)

    def queue_reanalysis_candidates(self, limit: int | None = None) -> int:
        """Move completed videos without market conclusions back to transcribed.

        Existing summaries and key points remain available until the analysis worker
        successfully replaces them.
        """

        limit_sql = ""
        params: list[Any] = []
        if limit is not None:
            limit_sql = " LIMIT %s"
            params.append(limit)

        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT v.id
            FROM videos AS v
            INNER JOIN transcripts AS t ON t.video_id = v.id
            LEFT JOIN analyses AS a ON a.video_id = v.id
            WHERE v.status IN ('done', 'analysis_failed')
              AND a.market_insights_json IS NULL
            ORDER BY v.id
            """
            + limit_sql,
            tuple(params),
        )
        ids = [int(row["id"]) for row in cursor.fetchall()]
        if not ids:
            cursor.close()
            return 0

        placeholders = ", ".join(["%s"] * len(ids))
        cursor.execute(
            f"""
            UPDATE videos
            SET status = 'transcribed',
                error_message = NULL
            WHERE id IN ({placeholders})
              AND status IN ('done', 'analysis_failed')
            """,
            tuple(ids),
        )
        updated = int(cursor.rowcount)
        cursor.close()
        self.connection.commit()
        return updated
