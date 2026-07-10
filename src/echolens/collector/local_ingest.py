"""Ingest local source videos into MySQL and Redis."""

from dataclasses import dataclass

from echolens.collector.local_models import LocalVideoItem
from echolens.storage.mysql import mysql_connection
from echolens.storage.redis_queue import VideoQueue
from echolens.storage.video_repository import VideoRepository, build_video_queue_payload


@dataclass(frozen=True)
class IngestResult:
    """Summary of one ingest run."""

    discovered: int
    inserted: int
    queued: int
    skipped_existing: int


class LocalIngestService:
    """Service that stores discovered videos and enqueues processing jobs."""

    def ingest(self, items: list[LocalVideoItem]) -> IngestResult:
        """Insert new videos into MySQL and push processing jobs to Redis."""

        inserted = 0
        queued = 0
        skipped_existing = 0
        queue = VideoQueue()

        with mysql_connection() as connection:
            repository = VideoRepository(connection)

            for item in items:
                if repository.video_exists(item):
                    skipped_existing += 1
                    continue

                creator_db_id = repository.ensure_creator(item)
                video_db_id = repository.insert_pending_video(item, creator_db_id)
                inserted += 1

                payload = build_video_queue_payload(item, video_db_id, creator_db_id)
                queue.push(payload)
                repository.mark_video_queued(video_db_id)
                queued += 1

            connection.commit()

        return IngestResult(
            discovered=len(items),
            inserted=inserted,
            queued=queued,
            skipped_existing=skipped_existing,
        )
