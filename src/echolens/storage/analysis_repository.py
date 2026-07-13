"""Persistence operations for the minimal LLM analysis stage."""

from datetime import datetime
import json
from typing import Any

from mysql.connector import MySQLConnection

from echolens.analysis.models import AnalysisResult


class AnalysisRepository:
    """Claim transcribed videos and persist structured analysis results."""

    def __init__(self, connection: MySQLConnection) -> None:
        self.connection = connection

    def claim_next_video(self) -> dict[str, Any] | None:
        """Claim the oldest transcribed video for LLM analysis."""

        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                v.id,
                v.video_id,
                v.description,
                t.transcript_text,
                t.language
            FROM videos AS v
            INNER JOIN transcripts AS t ON t.video_id = v.id
            WHERE v.status = %s
            ORDER BY v.id
            LIMIT 1
            FOR UPDATE
            """,
            ("transcribed",),
        )
        row = cursor.fetchone()
        if row is None:
            cursor.close()
            return None

        video_db_id = int(row["id"])
        cursor.execute(
            """
            UPDATE videos
            SET status = %s,
                updated_at = %s,
                error_message = NULL
            WHERE id = %s
              AND status = %s
            """,
            ("analyzing", datetime.now(), video_db_id, "transcribed"),
        )
        if cursor.rowcount != 1:
            cursor.close()
            return None

        cursor.close()
        return row

    def save_result(self, video_db_id: int, result: AnalysisResult, model_name: str) -> None:
        """Upsert analysis output and mark the video done."""

        now = datetime.now()
        cursor = self.connection.cursor()
        cursor.execute(
            """
            INSERT INTO analyses (
                video_id,
                summary,
                tags_json,
                key_points_json,
                model_name,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                summary = VALUES(summary),
                tags_json = VALUES(tags_json),
                key_points_json = VALUES(key_points_json),
                model_name = VALUES(model_name),
                updated_at = VALUES(updated_at)
            """,
            (
                video_db_id,
                result.summary,
                json.dumps(result.tags, ensure_ascii=False),
                json.dumps(result.key_points, ensure_ascii=False),
                model_name,
                now,
                now,
            ),
        )
        cursor.execute(
            """
            UPDATE videos
            SET status = %s,
                updated_at = %s,
                error_message = NULL
            WHERE id = %s
            """,
            ("done", now, video_db_id),
        )
        cursor.close()

    def mark_failed(self, video_db_id: int, error_message: str) -> None:
        """Record an analysis failure without automatic retry."""

        cursor = self.connection.cursor()
        cursor.execute(
            """
            UPDATE videos
            SET status = %s,
                updated_at = %s,
                error_message = %s
            WHERE id = %s
            """,
            ("analysis_failed", datetime.now(), error_message[:65535], video_db_id),
        )
        cursor.close()
