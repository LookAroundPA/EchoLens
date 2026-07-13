"""MySQL queries for frontend lists, processing jobs, and write actions."""

from __future__ import annotations

from datetime import datetime
import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mysql.connector import MySQLConnection
else:
    MySQLConnection = Any


class OperationConflict(RuntimeError):
    """Raised when a video cannot be moved into the requested processing stage."""


class ManagementRepository:
    """Provide video catalog queries and minimal operation persistence."""

    _VIDEO_SELECT = """
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

    def list_videos(
        self,
        *,
        query: str | None = None,
        creator_sec_uid: str | None = None,
        status: str | None = None,
        tag: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        conditions: list[str] = []
        params: list[Any] = []
        if query:
            pattern = f"%{query}%"
            conditions.append(
                "(COALESCE(v.description, '') LIKE %s OR COALESCE(a.summary, '') LIKE %s)"
            )
            params.extend([pattern, pattern])
        if creator_sec_uid:
            conditions.append("v.creator_sec_uid = %s")
            params.append(creator_sec_uid)
        if status:
            conditions.append("v.status = %s")
            params.append(status)
        if tag:
            conditions.append("JSON_CONTAINS(a.tags_json, JSON_QUOTE(%s))")
            params.append(tag)
        where_sql = " WHERE " + " AND ".join(conditions) if conditions else ""

        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT COUNT(*) AS total FROM videos AS v LEFT JOIN analyses AS a ON a.video_id = v.id"
            + where_sql,
            tuple(params),
        )
        total_row = cursor.fetchone() or {}
        total = int(total_row.get("total") or 0)
        cursor.execute(
            self._VIDEO_SELECT
            + where_sql
            + " ORDER BY COALESCE(v.source_create_time, 0) DESC, v.id DESC LIMIT %s OFFSET %s",
            tuple([*params, limit, offset]),
        )
        rows = cursor.fetchall()
        cursor.close()
        return rows, total

    def tag_rows(self, creator_sec_uid: str | None = None) -> list[dict[str, Any]]:
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

    def get_video_state(self, video_db_id: int) -> dict[str, Any] | None:
        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, status, file_path, audio_path
            FROM videos
            WHERE id = %s
            LIMIT 1
            """,
            (video_db_id,),
        )
        row = cursor.fetchone()
        cursor.close()
        return row

    def prepare_video(self, video_db_id: int, stage: str) -> str:
        """Reset one video to a requested stage and return the resolved stage."""

        row = self.get_video_state(video_db_id)
        if row is None:
            raise KeyError(f"Video {video_db_id} does not exist")

        status = str(row["status"])
        resolved = stage
        if stage == "current":
            if status in {"pending", "queued"}:
                resolved = "audio"
            elif status in {"audio_done", "transcription_failed"}:
                resolved = "transcription"
            elif status in {"transcribed", "analysis_failed"}:
                resolved = "analysis"
            elif status == "done":
                return "done"
            elif status in {"processing", "transcribing", "analyzing"}:
                raise OperationConflict(f"Video is already being processed: {status}")
            else:
                raise OperationConflict(f"Unsupported video status: {status}")

        cursor = self.connection.cursor()
        now = datetime.now()
        if resolved == "audio":
            cursor.execute("DELETE FROM analyses WHERE video_id = %s", (video_db_id,))
            cursor.execute("DELETE FROM transcripts WHERE video_id = %s", (video_db_id,))
            cursor.execute(
                """
                UPDATE videos
                SET status = 'queued', audio_path = NULL, audio_size = NULL,
                    audio_created_at = NULL, processed_at = NULL,
                    error_message = NULL, updated_at = %s
                WHERE id = %s
                """,
                (now, video_db_id),
            )
        elif resolved == "transcription":
            if not row.get("audio_path"):
                cursor.close()
                raise OperationConflict("Video has no extracted audio")
            cursor.execute("DELETE FROM analyses WHERE video_id = %s", (video_db_id,))
            cursor.execute("DELETE FROM transcripts WHERE video_id = %s", (video_db_id,))
            cursor.execute(
                "UPDATE videos SET status = 'audio_done', error_message = NULL, updated_at = %s WHERE id = %s",
                (now, video_db_id),
            )
        elif resolved == "analysis":
            cursor.execute("SELECT 1 FROM transcripts WHERE video_id = %s LIMIT 1", (video_db_id,))
            if cursor.fetchone() is None:
                cursor.close()
                raise OperationConflict("Video has no transcript")
            cursor.execute("DELETE FROM analyses WHERE video_id = %s", (video_db_id,))
            cursor.execute(
                "UPDATE videos SET status = 'transcribed', error_message = NULL, updated_at = %s WHERE id = %s",
                (now, video_db_id),
            )
        else:
            cursor.close()
            raise ValueError(f"Unsupported processing stage: {resolved}")
        cursor.close()
        return resolved

    def create_job(
        self,
        *,
        job_type: str,
        payload: dict[str, Any],
        video_id: int | None = None,
    ) -> dict[str, Any]:
        now = datetime.now()
        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(
            """
            INSERT INTO processing_jobs (
                video_id, job_type, status, retry_count, payload_json,
                created_at, updated_at
            ) VALUES (%s, %s, 'queued', 0, %s, %s, %s)
            """,
            (video_id, job_type, json.dumps(payload, ensure_ascii=False), now, now),
        )
        job_id = int(cursor.lastrowid)
        cursor.execute("SELECT * FROM processing_jobs WHERE id = %s", (job_id,))
        row = cursor.fetchone()
        cursor.close()
        if row is None:
            raise RuntimeError("Failed to create processing job")
        return row

    def get_job(self, job_id: int) -> dict[str, Any] | None:
        cursor = self.connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM processing_jobs WHERE id = %s LIMIT 1", (job_id,))
        row = cursor.fetchone()
        cursor.close()
        return row

    def list_jobs(
        self,
        *,
        status: str | None = None,
        job_type: str | None = None,
        video_id: int | None = None,
        limit: int = 50,
    ) -> tuple[list[dict[str, Any]], int]:
        conditions: list[str] = []
        params: list[Any] = []
        if status:
            conditions.append("status = %s")
            params.append(status)
        if job_type:
            conditions.append("job_type = %s")
            params.append(job_type)
        if video_id is not None:
            conditions.append("video_id = %s")
            params.append(video_id)
        where_sql = " WHERE " + " AND ".join(conditions) if conditions else ""
        cursor = self.connection.cursor(dictionary=True)
        cursor.execute("SELECT COUNT(*) AS total FROM processing_jobs" + where_sql, tuple(params))
        total_row = cursor.fetchone() or {}
        total = int(total_row.get("total") or 0)
        cursor.execute(
            "SELECT * FROM processing_jobs" + where_sql + " ORDER BY id DESC LIMIT %s",
            tuple([*params, limit]),
        )
        rows = cursor.fetchall()
        cursor.close()
        return rows, total

    def mark_job_running(self, job_id: int) -> None:
        now = datetime.now()
        cursor = self.connection.cursor()
        cursor.execute(
            """
            UPDATE processing_jobs
            SET status = 'running', started_at = %s, updated_at = %s,
                finished_at = NULL, error_message = NULL
            WHERE id = %s
            """,
            (now, now, job_id),
        )
        cursor.close()

    def mark_job_succeeded(self, job_id: int, result: dict[str, Any]) -> None:
        now = datetime.now()
        cursor = self.connection.cursor()
        cursor.execute(
            """
            UPDATE processing_jobs
            SET status = 'succeeded', result_json = %s, updated_at = %s,
                finished_at = %s, error_message = NULL
            WHERE id = %s
            """,
            (json.dumps(result, ensure_ascii=False), now, now, job_id),
        )
        cursor.close()

    def mark_job_failed(self, job_id: int, error_message: str) -> None:
        now = datetime.now()
        cursor = self.connection.cursor()
        cursor.execute(
            """
            UPDATE processing_jobs
            SET status = 'failed', updated_at = %s, finished_at = %s,
                error_message = %s
            WHERE id = %s
            """,
            (now, now, error_message[:65535], job_id),
        )
        cursor.close()
