from __future__ import annotations

import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from echolens.core.config import Settings
from echolens.semantic.service import SemanticIndexService
from echolens.semantic.store import SemanticStore


class FakeSource:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows

    def list_indexable_videos(self) -> list[dict]:
        return list(self.rows)

    def get_indexable_video(self, video_db_id: int) -> dict | None:
        return next((row for row in self.rows if int(row["id"]) == video_db_id), None)


class FakeEmbedder:
    def embed_documents(self, texts):
        return [self._vector(text) for text in texts]

    def embed_query(self, query: str):
        return self._vector(query)

    @staticmethod
    def _vector(text: str) -> tuple[float, ...]:
        values = [
            1.0 if any(word in text for word in ("人工智能", "AI", "效率", "重复工作")) else 0.0,
            1.0 if any(word in text for word in ("学习", "教育", "知识")) else 0.0,
            1.0 if any(word in text for word in ("做饭", "菜谱", "烹饪")) else 0.0,
        ]
        if not any(values):
            values = [0.1, 0.1, 0.1]
        norm = math.sqrt(sum(value * value for value in values))
        return tuple(value / norm for value in values)


def video_row(
    video_id: int,
    *,
    creator: str,
    title: str,
    summary: str,
    tags: list[str],
    segments: list[dict],
) -> dict:
    return {
        "id": video_id,
        "platform": "douyin",
        "video_id": f"source-{video_id}",
        "creator_sec_uid": creator,
        "creator_name": f"创作者 {creator}",
        "description": title,
        "source_create_time": 1_720_000_000 + video_id,
        "status": "done",
        "updated_at": "2026-07-14 10:00:00",
        "transcript_text": "".join(item["text"] for item in segments),
        "segments_json": json.dumps(segments, ensure_ascii=False),
        "transcript_updated_at": "2026-07-14 10:00:00",
        "summary": summary,
        "tags_json": json.dumps(tags, ensure_ascii=False),
        "key_points_json": json.dumps([summary], ensure_ascii=False),
        "analysis_updated_at": "2026-07-14 10:00:00",
    }


class SemanticServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.path = Path(self.temporary.name) / "semantic.sqlite3"
        self.rows = [
            video_row(
                1,
                creator="creator-ai",
                title="让人工智能处理重复工作",
                summary="把重复劳动交给人工智能，提高工作效率。",
                tags=["AI", "效率"],
                segments=[
                    {"start": 0, "end": 6, "text": "把重复工作交给人工智能"},
                    {"start": 6, "end": 12, "text": "人应该专注判断和创造"},
                ],
            ),
            video_row(
                2,
                creator="creator-food",
                title="家常菜做法",
                summary="介绍一道简单菜谱。",
                tags=["烹饪"],
                segments=[
                    {"start": 0, "end": 7, "text": "先准备食材再开始做饭"},
                ],
            ),
        ]
        self.settings = Settings(
            semantic_model="fake-model",
            semantic_index_path=self.path,
            semantic_auto_sync=False,
            semantic_min_score=0.0,
            semantic_max_chunks_per_video=2,
        )
        self.source = FakeSource(self.rows)
        self.service = SemanticIndexService(
            self.settings,
            source=self.source,
            embedder=FakeEmbedder(),
            store=SemanticStore(self.path),
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_incremental_sync_and_hybrid_search(self) -> None:
        first = self.service.sync()
        second = self.service.sync()
        status = self.service.status()

        self.assertEqual(first.indexed, 2)
        self.assertGreaterEqual(first.chunks, 4)
        self.assertEqual(second.indexed, 0)
        self.assertEqual(second.skipped, 2)
        self.assertTrue(status.ready)
        self.assertEqual(status.video_count, 2)

        results = self.service.search("怎样提高效率", limit=5, ensure_synced=False)
        self.assertTrue(results)
        self.assertEqual(results[0].chunk.video_id, 1)
        self.assertEqual(results[0].chunk.creator_sec_uid, "creator-ai")
        self.assertIsNotNone(results[0].chunk.start)

    def test_creator_and_tag_filters_keep_sources_scoped(self) -> None:
        self.service.sync()

        creator_results = self.service.search(
            "工作方法",
            creator_sec_uid="creator-food",
            limit=10,
            ensure_synced=False,
        )
        tag_results = self.service.search(
            "工作方法",
            tag="AI",
            limit=10,
            ensure_synced=False,
        )

        self.assertTrue(creator_results)
        self.assertTrue(all(item.chunk.creator_sec_uid == "creator-food" for item in creator_results))
        self.assertTrue(tag_results)
        self.assertTrue(all("AI" in item.chunk.tags for item in tag_results))

    def test_changed_and_removed_videos_update_existing_index(self) -> None:
        self.service.sync()
        self.rows[0]["analysis_updated_at"] = "2026-07-14 11:00:00"
        self.rows[0]["summary"] = "人工智能也可以帮助学习。"
        changed = self.service.sync()

        self.assertEqual(changed.indexed, 1)
        self.assertEqual(changed.skipped, 1)

        self.source.rows = [self.rows[0]]
        removed = self.service.sync()
        self.assertEqual(removed.removed, 1)
        self.assertEqual(self.service.status().video_count, 1)


if __name__ == "__main__":
    unittest.main()
