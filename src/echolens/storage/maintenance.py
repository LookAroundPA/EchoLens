"""Small, idempotent MySQL maintenance operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mysql.connector import MySQLConnection
else:
    MySQLConnection = Any


MARKET_INSIGHTS_COLUMN = "market_insights_json"

INTELLIGENCE_TABLE_STATEMENTS: tuple[tuple[str, str], ...] = (
    (
        "topics",
        """
        CREATE TABLE IF NOT EXISTS topics (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            canonical_name VARCHAR(255) NOT NULL,
            normalized_name VARCHAR(255) NOT NULL,
            topic_type VARCHAR(32) NOT NULL,
            status VARCHAR(32) NOT NULL DEFAULT 'pending',
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            UNIQUE KEY uq_topics_type_normalized (topic_type, normalized_name),
            KEY idx_topics_status (status)
        )
        """,
    ),
    (
        "topic_aliases",
        """
        CREATE TABLE IF NOT EXISTS topic_aliases (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            topic_id BIGINT UNSIGNED NOT NULL,
            alias VARCHAR(255) NOT NULL,
            normalized_alias VARCHAR(255) NOT NULL,
            source VARCHAR(32) NOT NULL,
            created_at DATETIME NOT NULL,
            UNIQUE KEY uq_topic_aliases_topic_normalized (topic_id, normalized_alias),
            KEY idx_topic_aliases_normalized (normalized_alias),
            KEY idx_topic_aliases_topic (topic_id)
        )
        """,
    ),
    (
        "creator_topic_opinions",
        """
        CREATE TABLE IF NOT EXISTS creator_topic_opinions (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            creator_id BIGINT UNSIGNED NOT NULL,
            video_id BIGINT UNSIGNED NOT NULL,
            analysis_id BIGINT UNSIGNED NOT NULL,
            insight_index INT UNSIGNED NOT NULL,
            topic_id BIGINT UNSIGNED NOT NULL,
            raw_subject VARCHAR(255) NOT NULL,
            match_method VARCHAR(32) NOT NULL,
            match_confidence VARCHAR(16) NOT NULL,
            stance VARCHAR(32) NOT NULL,
            source_type VARCHAR(16) NOT NULL,
            time_horizon VARCHAR(32) NOT NULL,
            confidence VARCHAR(16) NOT NULL,
            conclusion TEXT NOT NULL,
            reasoning_json JSON NULL,
            risks_json JSON NULL,
            evidence_quote TEXT NULL,
            published_at DATETIME NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            UNIQUE KEY uq_creator_topic_opinions_analysis_index (analysis_id, insight_index),
            KEY idx_creator_topic_opinions_creator_topic_time (
                creator_id,
                topic_id,
                published_at
            ),
            KEY idx_creator_topic_opinions_topic_time (topic_id, published_at),
            KEY idx_creator_topic_opinions_video (video_id)
        )
        """,
    ),
    (
        "opinion_changes",
        """
        CREATE TABLE IF NOT EXISTS opinion_changes (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            creator_id BIGINT UNSIGNED NOT NULL,
            topic_id BIGINT UNSIGNED NOT NULL,
            previous_opinion_id BIGINT UNSIGNED NULL,
            current_opinion_id BIGINT UNSIGNED NOT NULL,
            change_type VARCHAR(32) NOT NULL,
            previous_stance VARCHAR(32) NULL,
            current_stance VARCHAR(32) NOT NULL,
            change_summary TEXT NOT NULL,
            detected_at DATETIME NOT NULL,
            UNIQUE KEY uq_opinion_changes_current (current_opinion_id),
            KEY idx_opinion_changes_creator_topic_time (
                creator_id,
                topic_id,
                detected_at
            ),
            KEY idx_opinion_changes_topic_time (topic_id, detected_at)
        )
        """,
    ),
)


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

    def ensure_intelligence_schema(self) -> list[str]:
        """Create the normalized intelligence tables when they are absent."""

        created: list[str] = []
        cursor = self.connection.cursor(dictionary=True)
        for table_name, statement in INTELLIGENCE_TABLE_STATEMENTS:
            cursor.execute(
                """
                SELECT COUNT(*) AS table_count
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = %s
                """,
                (table_name,),
            )
            row = cursor.fetchone() or {}
            if int(row.get("table_count") or 0) > 0:
                continue
            cursor.execute(statement)
            created.append(table_name)
        cursor.close()
        if created:
            self.connection.commit()
        return created

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
