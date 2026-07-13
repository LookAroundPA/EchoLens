"""Repository methods for creator and video ingest state."""

from datetime import datetime
import json
from typing import Any

from mysql.connector import MySQLConnection

from echolens.collector.local_models import LocalVideoItem


class VideoRepository:
    """Persistence operations for local video ingest."""

    def __init__(self, connection: MySQLConnection) -> None:
        self.connection = connection

    def ensure_creator(self, item: LocalVideoItem) -> int:
        """Ensure a creator exists using ``platform + sec_uid`` as identity."""

        now = datetime.now()
        cursor = self.connection.cursor(dictionary=True)

        # Backfill rows created before sec_uid became the canonical creator key.
        cursor.execute(
            """
            UPDATE creators
            SET sec_uid = %s,
                platform_uid = %s,
                provider_author_id = %s,
                creator_name = %s,
                source_dir = %s,
                updated_at = %s
            WHERE platform = %s
              AND sec_uid IS NULL
              AND provider_author_id = %s
            """,
            (
                item.creator_sec_uid,
                item.author_uid,
                item.provider_author_id,
                item.creator_name,
                str(item.source_path.parent),
                now,
                item.platform,
                item.provider_author_id,
            ),
        )

        cursor.execute(
            """
            INSERT INTO creators (
                platform,
                sec_uid,
                platform_uid,
                provider_author_id,
                creator_name,
                source_dir,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                platform_uid = VALUES(platform_uid),
                provider_author_id = VALUES(provider_author_id),
                creator_name = VALUES(creator_name),
                source_dir = VALUES(source_dir),
                updated_at = VALUES(updated_at)
            """,
            (
                item.platform,
                item.creator_sec_uid,
                item.author_uid,
                item.provider_author_id,
                item.creator_name,
                str(item.source_path.parent),
                now,
                now,
            ),
        )
        cursor.execute(
            """
            SELECT id FROM creators
            WHERE platform = %s AND sec_uid = %s
            LIMIT 1
            """,
            (item.platform, item.creator_sec_uid),
        )
        row = cursor.fetchone()
        cursor.close()
        if row is None:
            raise RuntimeError("Failed to ensure creator row.")
        return int(row["id"])

    def video_exists(self, item: LocalVideoItem, creator_db_id: int) -> bool:
        """Return whether a video exists and backfill a legacy identity row."""

        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id FROM videos
            WHERE platform = %s AND creator_sec_uid = %s AND video_id = %s
            LIMIT 1
            """,
            item.dedupe_key,
        )
        row = cursor.fetchone()
        if row is not None:
            cursor.close()
            return True

        cursor.execute(
            """
            SELECT id FROM videos
            WHERE platform = %s
              AND creator_id = %s
              AND video_id = %s
              AND creator_sec_uid IS NULL
            LIMIT 1
            """,
            (item.platform, creator_db_id, item.video_id),
        )
        legacy_row = cursor.fetchone()
        if legacy_row is None:
            cursor.close()
            return False

        cursor.execute(
            """
            UPDATE videos
            SET creator_sec_uid = %s,
                provider_author_id = %s,
                author_uid = %s,
                statistics_json = %s,
                metadata_json = %s,
                updated_at = %s
            WHERE id = %s
            """,
            (
                item.creator_sec_uid,
                item.provider_author_id,
                item.author_uid,
                json.dumps(item.statistics, ensure_ascii=False),
                json.dumps(item.raw_metadata, ensure_ascii=False),
                datetime.now(),
                int(legacy_row["id"]),
            ),
        )
        cursor.close()
        return True

    def insert_pending_video(self, item: LocalVideoItem, creator_db_id: int) -> int:
        """Insert a pending video row and return its database id."""

        cursor = self.connection.cursor(dictionary=True)
        now = datetime.now()
        cursor.execute(
            """
            INSERT INTO videos (
                platform,
                creator_sec_uid,
                provider_author_id,
                author_uid,
                video_id,
                creator_id,
                file_path,
                metadata_path,
                file_name,
                file_size,
                file_mtime,
                description,
                source_create_time,
                downloaded_at,
                statistics_json,
                metadata_json,
                status,
                created_at,
                updated_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            """,
            (
                item.platform,
                item.creator_sec_uid,
                item.provider_author_id,
                item.author_uid,
                item.video_id,
                creator_db_id,
                str(item.source_path),
                str(item.metadata_path),
                item.file_name,
                item.file_size,
                item.file_mtime,
                item.desc,
                item.create_time,
                item.downloaded_at,
                json.dumps(item.statistics, ensure_ascii=False),
                json.dumps(item.raw_metadata, ensure_ascii=False),
                "pending",
                now,
                now,
            ),
        )
        video_db_id = int(cursor.lastrowid)
        cursor.close()
        return video_db_id

    def mark_video_queued(self, video_db_id: int) -> None:
        """Mark a video as queued."""

        cursor = self.connection.cursor()
        cursor.execute(
            """
            UPDATE videos
            SET status = %s, updated_at = %s
            WHERE id = %s
            """,
            ("queued", datetime.now(), video_db_id),
        )
        cursor.close()

    def get_video(self, video_db_id: int) -> dict[str, Any] | None:
        """Return one video row by its EchoLens database id."""

        cursor = self.connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM videos WHERE id = %s LIMIT 1", (video_db_id,))
        row = cursor.fetchone()
        cursor.close()
        return row

    def claim_video_for_audio(self, video_db_id: int) -> dict[str, Any] | None:
        """Atomically transition a queued video to processing and return its row."""

        cursor = self.connection.cursor()
        cursor.execute(
            """
            UPDATE videos
            SET status = %s, updated_at = %s, error_message = NULL
            WHERE id = %s AND status = %s
            """,
            ("processing", datetime.now(), video_db_id, "queued"),
        )
        claimed = cursor.rowcount == 1
        cursor.close()
        if not claimed:
            return None
        return self.get_video(video_db_id)

    def mark_audio_done(self, video_db_id: int, audio_path: str, audio_size: int) -> None:
        """Persist a completed WAV output and finalize the audio stage."""

        cursor = self.connection.cursor()
        now = datetime.now()
        cursor.execute(
            """
            UPDATE videos
            SET status = %s,
                audio_path = %s,
                audio_size = %s,
                audio_created_at = %s,
                processed_at = %s,
                updated_at = %s,
                error_message = NULL
            WHERE id = %s
            """,
            ("audio_done", audio_path, audio_size, now, now, now, video_db_id),
        )
        cursor.close()

    def release_video_for_retry(self, video_db_id: int, error_message: str) -> None:
        """Return a failed audio job to queued and retain its failure detail."""

        cursor = self.connection.cursor()
        cursor.execute(
            """
            UPDATE videos
            SET status = %s, updated_at = %s, error_message = %s
            WHERE id = %s
            """,
            ("queued", datetime.now(), error_message[:65535], video_db_id),
        )
        cursor.close()


def build_video_queue_payload(item: LocalVideoItem, video_db_id: int, creator_db_id: int) -> dict[str, Any]:
    """Build a Redis payload for video processing."""

    return {
        "video_db_id": video_db_id,
        "creator_db_id": creator_db_id,
        "platform": item.platform,
        "creator_sec_uid": item.creator_sec_uid,
        "provider_author_id": item.provider_author_id,
        "video_id": item.video_id,
        "source_path": str(item.source_path),
        "metadata_path": str(item.metadata_path),
    }
