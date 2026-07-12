"""Redis queue helpers for EchoLens."""

import json
from typing import Any

import redis
from redis import Redis

from echolens.core.config import Settings, get_settings


def redis_client(settings: Settings | None = None) -> Redis:
    """Create a Redis client from runtime settings."""

    runtime_settings = settings or get_settings()
    return redis.Redis(
        host=runtime_settings.redis_host,
        port=runtime_settings.redis_port,
        password=runtime_settings.redis_password,
        db=runtime_settings.redis_db,
        decode_responses=True,
    )


class VideoQueue:
    """Queue wrapper for video processing jobs."""

    def __init__(self, client: Redis | None = None, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.client = client or redis_client(self.settings)

    def push(self, payload: dict[str, Any]) -> int:
        """Push a video task and return the queue length."""

        return self.client.rpush(self.settings.redis_video_queue, json.dumps(payload, ensure_ascii=False))

    def pop(self, timeout: int = 5) -> dict[str, Any] | None:
        """Pop one video task from the queue."""

        item = self.client.blpop(self.settings.redis_video_queue, timeout=timeout)
        if item is None:
            return None
        _, payload = item
        return json.loads(payload)

    def reserve(self, timeout: int = 5) -> tuple[str, dict[str, Any]] | None:
        """Atomically move one task to the processing queue and return it."""

        payload = self.client.brpoplpush(
            self.settings.redis_video_queue,
            self.settings.redis_video_processing_queue,
            timeout=timeout,
        )
        if payload is None:
            return None
        return payload, json.loads(payload)

    def acknowledge(self, raw_payload: str) -> None:
        """Remove a successfully handled task from the processing queue."""

        self.client.lrem(self.settings.redis_video_processing_queue, 1, raw_payload)

    def retry(self, raw_payload: str) -> None:
        """Return a failed task to the ready queue without losing it."""

        pipeline = self.client.pipeline()
        pipeline.lrem(self.settings.redis_video_processing_queue, 1, raw_payload)
        pipeline.rpush(self.settings.redis_video_queue, raw_payload)
        pipeline.execute()
