"""Small write repository for manual transcript and analysis edits."""

from __future__ import annotations

from datetime import datetime
import json
from typing import TYPE_CHECKING, Any

from echolens.intelligence.repository import IntelligenceRepository

if TYPE_CHECKING:
    from mysql.connector import MySQLConnection
else:
    MySQLConnection = Any


class ContentRepository:
    """Persist user edits without adding a separate revision system."""

    def __init__(self, connection: MySQLConnection) -> None:
        self.connection = connection

    def update_transcript(self, video_db_id: int, transcript: str) -> None:
        now = datetime.now()
        cursor = self.connection.cursor(dictionary=True)
        try:
            cursor.execute("SELECT id FROM videos WHERE id = %s LIMIT 1", (video_db_id,))
            if cursor.fetchone() is None:
                raise KeyError(f"Video {video_db_id} does not exist")

            cursor.execute(
                "SELECT id FROM transcripts WHERE video_id = %s LIMIT 1",
                (video_db_id,),
            )
            if cursor.fetchone() is None:
                cursor.execute(
                    """
                    INSERT INTO transcripts (
                        video_id, transcript_text, segments_json, language,
                        model_name, created_at, updated_at
                    ) VALUES (%s, %s, NULL, NULL, 'manual', %s, %s)
                    """,
                    (video_db_id, transcript, now, now),
                )
            else:
                cursor.execute(
                    """
                    UPDATE transcripts
                    SET transcript_text = %s, updated_at = %s
                    WHERE video_id = %s
                    """,
                    (transcript, now, video_db_id),
                )

            cursor.execute(
                """
                UPDATE videos
                SET status = 'transcribed', error_message = NULL, updated_at = %s
                WHERE id = %s
                """,
                (now, video_db_id),
            )
            IntelligenceRepository(self.connection).remove_video_analysis(video_db_id)
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise
        finally:
            cursor.close()

    def update_analysis(
        self,
        video_db_id: int,
        *,
        summary: str,
        tags: list[str],
        key_points: list[str],
    ) -> None:
        now = datetime.now()
        cursor = self.connection.cursor(dictionary=True)
        try:
            cursor.execute("SELECT id, status FROM videos WHERE id = %s LIMIT 1", (video_db_id,))
            video = cursor.fetchone()
            if video is None:
                raise KeyError(f"Video {video_db_id} does not exist")
            clear_market_insights = str(video.get("status") or "") != "done"

            cursor.execute(
                "SELECT id FROM transcripts WHERE video_id = %s LIMIT 1",
                (video_db_id,),
            )
            if cursor.fetchone() is None:
                raise ValueError("Video has no transcript")

            cursor.execute(
                "SELECT id FROM analyses WHERE video_id = %s LIMIT 1",
                (video_db_id,),
            )
            encoded_tags = json.dumps(tags, ensure_ascii=False)
            encoded_key_points = json.dumps(key_points, ensure_ascii=False)
            if cursor.fetchone() is None:
                cursor.execute(
                    """
                    INSERT INTO analyses (
                        video_id, summary, tags_json, key_points_json,
                        market_insights_json, model_name, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, 'manual', %s, %s)
                    """,
                    (
                        video_db_id,
                        summary,
                        encoded_tags,
                        encoded_key_points,
                        json.dumps([], ensure_ascii=False),
                        now,
                        now,
                    ),
                )
            elif clear_market_insights:
                cursor.execute(
                    """
                    UPDATE analyses
                    SET summary = %s,
                        tags_json = %s,
                        key_points_json = %s,
                        market_insights_json = %s,
                        model_name = 'manual',
                        updated_at = %s
                    WHERE video_id = %s
                    """,
                    (
                        summary,
                        encoded_tags,
                        encoded_key_points,
                        json.dumps([], ensure_ascii=False),
                        now,
                        video_db_id,
                    ),
                )
            else:
                cursor.execute(
                    """
                    UPDATE analyses
                    SET summary = %s, tags_json = %s, key_points_json = %s,
                        updated_at = %s
                    WHERE video_id = %s
                    """,
                    (
                        summary,
                        encoded_tags,
                        encoded_key_points,
                        now,
                        video_db_id,
                    ),
                )

            cursor.execute(
                """
                UPDATE videos
                SET status = 'done', processed_at = %s, error_message = NULL,
                    updated_at = %s
                WHERE id = %s
                """,
                (now, now, video_db_id),
            )
            if clear_market_insights:
                IntelligenceRepository(self.connection).remove_video_analysis(video_db_id)
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise
        finally:
            cursor.close()
