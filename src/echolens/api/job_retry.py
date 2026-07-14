"""Create retry jobs while preserving failed task history."""

from __future__ import annotations

from datetime import datetime
import json
from typing import Any

from echolens.api.models import JobStatus, ProcessingJob, processing_job_from_row
from echolens.core.config import Settings, get_settings
from echolens.storage.mysql import mysql_connection


class JobRetryConflict(RuntimeError):
    """Raised when a processing job cannot be retried."""


class JobRetryService:
    """Create a new queued job from one failed frontend operation."""

    _SUPPORTED_JOB_TYPES = {"scan", "pipeline", "video_process", "video_batch", "semantic_index"}

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def retry(self, job_id: int) -> ProcessingJob | None:
        """Clone one failed job, incrementing its retry count."""

        with mysql_connection(self.settings) as connection:
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                "SELECT * FROM processing_jobs WHERE id = %s LIMIT 1 FOR UPDATE",
                (job_id,),
            )
            row = cursor.fetchone()
            if row is None:
                cursor.close()
                return None

            source_job = processing_job_from_row(row)
            if source_job.status != JobStatus.failed:
                cursor.close()
                raise JobRetryConflict(
                    f"Only failed jobs can be retried; current status is {source_job.status.value}"
                )
            if source_job.job_type not in self._SUPPORTED_JOB_TYPES:
                cursor.close()
                raise JobRetryConflict(f"Unsupported job type: {source_job.job_type}")

            now = datetime.now()
            cursor.execute(
                """
                INSERT INTO processing_jobs (
                    video_id, job_type, status, retry_count, payload_json,
                    created_at, updated_at
                ) VALUES (%s, %s, 'queued', %s, %s, %s, %s)
                """,
                (
                    source_job.video_id,
                    source_job.job_type,
                    source_job.retry_count + 1,
                    json.dumps(source_job.payload, ensure_ascii=False),
                    now,
                    now,
                ),
            )
            retry_job_id = int(cursor.lastrowid)
            cursor.execute(
                "SELECT * FROM processing_jobs WHERE id = %s LIMIT 1",
                (retry_job_id,),
            )
            retry_row: dict[str, Any] | None = cursor.fetchone()
            cursor.close()
            connection.commit()

        if retry_row is None:
            raise RuntimeError("Failed to create retry job")
        return processing_job_from_row(retry_row)
