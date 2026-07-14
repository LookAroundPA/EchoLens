"""Redis queue for frontend-triggered EchoLens operations."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from redis import Redis

from echolens.core.config import Settings, get_settings
from echolens.storage.redis_queue import redis_client


@dataclass(frozen=True)
class ReservedOperation:
    """One operation message reserved from Redis."""

    raw_payload: str
    job_id: int
    job_type: str
    payload: dict[str, Any]


class OperationQueue:
    """Small reliable-list queue compatible with Redis 3.x."""

    def __init__(self, client: Redis | None = None, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.client = client or redis_client(self.settings)

    def push(self, *, job_id: int, job_type: str, payload: dict[str, Any]) -> int:
        message = json.dumps(
            {
                "jobId": job_id,
                "jobType": job_type,
                "payload": payload,
            },
            ensure_ascii=False,
        )
        return int(self.client.rpush(self.settings.redis_operation_queue, message))

    def reserve(self, timeout: int = 5) -> ReservedOperation | None:
        raw_payload = self.client.brpoplpush(
            self.settings.redis_operation_queue,
            self.settings.redis_operation_processing_queue,
            timeout=timeout,
        )
        if raw_payload is None:
            return None

        try:
            value = json.loads(raw_payload)
            if not isinstance(value, dict):
                raise ValueError("Operation message must be an object")
            payload = value.get("payload")
            if not isinstance(payload, dict):
                raise ValueError("Operation payload must be an object")
            return ReservedOperation(
                raw_payload=raw_payload,
                job_id=int(value["jobId"]),
                job_type=str(value["jobType"]),
                payload=payload,
            )
        except Exception:
            self.acknowledge(raw_payload)
            raise

    def acknowledge(self, raw_payload: str) -> None:
        self.client.lrem(self.settings.redis_operation_processing_queue, 1, raw_payload)

    def retry(self, raw_payload: str) -> None:
        pipeline = self.client.pipeline()
        pipeline.lrem(self.settings.redis_operation_processing_queue, 1, raw_payload)
        pipeline.rpush(self.settings.redis_operation_queue, raw_payload)
        pipeline.execute()

    def recover_reserved(self) -> int:
        """Return messages left reserved by a stopped single worker to the ready queue."""

        recovered = 0
        while True:
            raw_payload = self.client.rpoplpush(
                self.settings.redis_operation_processing_queue,
                self.settings.redis_operation_queue,
            )
            if raw_payload is None:
                return recovered
            recovered += 1
