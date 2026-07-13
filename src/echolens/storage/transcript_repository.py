"""Persistence operations for the minimal transcription stage."""

from datetime import datetime
import json
from typing import Any

from mysql.connector import MySQLConnection

from echolens.speech.faster_whisper import TranscriptionResult


class TranscriptRepository:
    """Claim audio-complete videos and persist transcript results."""

    def __init__(self, connection: MySQLConnection) -> None:
        self.connection = connection

    def claim_next_video(self) -> dict[str, Any] | None:
        """Claim the oldest audio-complete video for transcription."""

        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id
            FROM videos
            WHERE status = %s
              AND audio_path IS NOT NULL
            ORDER BY id
            LIMIT 1
            FOR UPDATE
            """,
            ("audio_done",),
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
            ("transcribing", datetime.now(), video_db_id, "audio_done"),
        )
        if cursor.rowcount != 1:
            cursor.close()
            return None

        cursor.execute("SELECT * FROM videos WHERE id = %s LIMIT 1", (video_db_id,))
        video = cursor.fetchone()
        cursor.close()
        return video

    def save_result(self, video_db_id: int, result: TranscriptionResult) -> None:
        """Upsert a transcript and mark its video as transcribed."""

        now = datetime.now()
        segments_json = json.dumps(
            [segment.as_dict() for segment in result.segments],
            ensure_ascii=False,
        )
        cursor = self.connection.cursor()
        cursor.execute(
            """
            INSERT INTO transcripts (
                video_id,
                transcript_text,
                segments_json,
                language,
                model_name,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                transcript_text = VALUES(transcript_text),
                segments_json = VALUES(segments_json),
                language = VALUES(language),
                model_name = VALUES(model_name),
                updated_at = VALUES(updated_at)
            """,
            (
                video_db_id,
                result.text,
                segments_json,
                result.language,
                result.model_name,
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
            ("transcribed", now, video_db_id),
        )
        cursor.close()

    def mark_failed(self, video_db_id: int, error_message: str) -> None:
        """Record a transcription failure without automatic retry."""

        cursor = self.connection.cursor()
        cursor.execute(
            """
            UPDATE videos
            SET status = %s,
                updated_at = %s,
                error_message = %s
            WHERE id = %s
            """,
            (
                "transcription_failed",
                datetime.now(),
                error_message[:65535],
                video_db_id,
            ),
        )
        cursor.close()
