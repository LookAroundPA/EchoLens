"""Tests for the Redis List operation queue protocol."""

import json
import unittest

from echolens.core.config import Settings
from echolens.storage.operation_queue import OperationQueue


class FakePipeline:
    def __init__(self, client: "FakeRedis") -> None:
        self.client = client

    def lrem(self, key: str, count: int, value: str) -> "FakePipeline":
        self.client.events.append(("lrem", key, count, value))
        return self

    def rpush(self, key: str, value: str) -> "FakePipeline":
        self.client.events.append(("rpush", key, value))
        return self

    def execute(self) -> None:
        self.client.events.append(("execute",))


class FakeRedis:
    def __init__(self) -> None:
        self.events: list[tuple] = []
        self.reserved_payload: str | None = None
        self.recovery_payloads: list[str | None] = []

    def rpush(self, key: str, value: str) -> int:
        self.events.append(("rpush", key, value))
        return 1

    def brpoplpush(self, source: str, destination: str, timeout: int) -> str | None:
        self.events.append(("brpoplpush", source, destination, timeout))
        return self.reserved_payload

    def lrem(self, key: str, count: int, value: str) -> int:
        self.events.append(("lrem", key, count, value))
        return 1

    def pipeline(self) -> FakePipeline:
        return FakePipeline(self)

    def rpoplpush(self, source: str, destination: str) -> str | None:
        self.events.append(("rpoplpush", source, destination))
        return self.recovery_payloads.pop(0)


class OperationQueueTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = Settings(
            redis_operation_queue="test:operations",
            redis_operation_processing_queue="test:operations:processing",
        )
        self.client = FakeRedis()
        self.queue = OperationQueue(client=self.client, settings=self.settings)

    def test_push_and_reserve_preserve_job_message(self) -> None:
        length = self.queue.push(
            job_id=8,
            job_type="pipeline",
            payload={"scan": True, "maxTasks": 3},
        )
        raw = self.client.events[0][2]
        self.client.reserved_payload = raw

        reserved = self.queue.reserve(timeout=2)

        self.assertEqual(length, 1)
        self.assertIsNotNone(reserved)
        assert reserved is not None
        self.assertEqual(reserved.job_id, 8)
        self.assertEqual(reserved.job_type, "pipeline")
        self.assertEqual(reserved.payload, {"scan": True, "maxTasks": 3})
        self.assertEqual(json.loads(raw)["jobId"], 8)

    def test_acknowledge_and_retry_use_processing_queue(self) -> None:
        self.queue.acknowledge("message")
        self.queue.retry("message")

        self.assertIn(
            ("lrem", "test:operations:processing", 1, "message"),
            self.client.events,
        )
        self.assertIn(("rpush", "test:operations", "message"), self.client.events)
        self.assertIn(("execute",), self.client.events)

    def test_recovers_every_reserved_message(self) -> None:
        self.client.recovery_payloads = ["one", "two", None]

        recovered = self.queue.recover_reserved()

        self.assertEqual(recovered, 2)

    def test_malformed_message_is_removed_from_processing_queue(self) -> None:
        self.client.reserved_payload = "not-json"

        with self.assertRaises(json.JSONDecodeError):
            self.queue.reserve(timeout=1)

        self.assertIn(
            ("lrem", "test:operations:processing", 1, "not-json"),
            self.client.events,
        )


if __name__ == "__main__":
    unittest.main()
