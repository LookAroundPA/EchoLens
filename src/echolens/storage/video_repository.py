"""Repository methods for creator and video ingest state."""

from datetime import datetime
from typing import Any

from mysql.connector import MySQLConnection

from echolens.collector.local_models import LocalVideoItem


class VideoRepository:
    """Persistence operations for local video ingest."""

    def __init__(self, connection: MySQLConnection) -> None:
        self.connection = connection

    def ensure_creator(self, item: LocalVideoItem) -> int:
        """Ensure a creator row exists and return its database id."""

        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(
            """
            INSERT INTO creators (platform, author_id, creator_name, source_dir, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                source_dir = VALUES(source_dir),
                updated_at = VALUES(updated_at)
            """,
            (
                item.platform,
                item.author_id,
                item.source_path.parent.name,
                str(item.source_path.parent),
                datetime.now(),
                datetime.now(),
            ),
        )
        cursor.execute(
            """
            SELECT id FROM creators
            WHERE platform = %s AND author_id = %s
            LIMIT 1
            """,
            (item.platform, item.author_id),
        )
        row = cursor.fetchone()
        cursor.close()
        if row is None:
            raise RuntimeError("Failed to ensure creator row.")
        return int(row["id"])

    def video_exists(self, item: LocalVideoItem) -> bool:
        """Return whether a video already exists by primary dedupe key."""

        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id FROM videos
            WHERE platform = %s AND author_id = %s AND video_id = %s
            LIMIT 1
            """,
            item.dedupe_key,
        )
        row = cursor.fetchone()
        cursor.close()
        return row is not None

    def insert_pending_video(self, item: LocalVideoItem, creator_db_id: int) -> int:
        """Insert a pending video row and return its database id."""

        cursor = self.connection.cursor(dictionary=True)
        now = datetime.now()
        cursor.execute(
            """
            INSERT INTO videos (
                platform,
                author_id,
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
                status,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                item.platform,
                item.author_id,
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


def build_video_queue_payload(item: LocalVideoItem, video_db_id: int, creator_db_id: int) -> dict[str, Any]:
    """Build a Redis payload for video processing."""

    return {
        "video_db_id": video_db_id,
        "creator_db_id": creator_db_id,
        "platform": item.platform,
        "author_id": item.author_id,
        "video_id": item.video_id,
        "source_path": str(item.source_path),
        "metadata_path": str(item.metadata_path),
    }
