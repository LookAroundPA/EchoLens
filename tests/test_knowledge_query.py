"""Tests for the minimal knowledge query layer."""

import json
import unittest

from echolens.knowledge.formatters import render_item_markdown, render_json
from echolens.knowledge.models import KnowledgeItem
from echolens.storage.knowledge_repository import KnowledgeRepository


ROW = {
    "db_id": 7,
    "platform": "douyin",
    "video_id": "7103",
    "creator_sec_uid": "MS4w.test",
    "creator_name": "测试创作者",
    "description": "视频描述",
    "source_create_time": 1710000000,
    "status": "done",
    "summary": "这是摘要",
    "tags_json": '["AI", "知识"]',
    "key_points_json": '["观点一", "观点二"]',
    "analysis_model": "deepseek-v4-flash",
    "language": "zh",
    "transcript_text": "完整转写内容",
}


class FakeCursor:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows
        self.sql = ""
        self.params: tuple[object, ...] = ()

    def execute(self, sql: str, params: tuple[object, ...]) -> None:
        self.sql = sql
        self.params = params

    def fetchall(self) -> list[dict[str, object]]:
        return self.rows

    def close(self) -> None:
        pass


class FakeConnection:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.cursor_instance = FakeCursor(rows)

    def cursor(self, dictionary: bool = False) -> FakeCursor:
        assert dictionary
        return self.cursor_instance


class KnowledgeQueryTests(unittest.TestCase):
    def test_normalizes_mysql_json_and_renders_detail(self) -> None:
        item = KnowledgeItem.from_row(ROW)

        self.assertEqual(item.tags, ["AI", "知识"])
        self.assertEqual(item.key_points, ["观点一", "观点二"])
        markdown = render_item_markdown(item)
        self.assertIn("这是摘要", markdown)
        self.assertIn("完整转写内容", markdown)
        self.assertEqual(json.loads(render_json(item))["video_id"], "7103")

    def test_builds_creator_tag_and_keyword_filters(self) -> None:
        connection = FakeConnection([ROW])
        items = KnowledgeRepository(connection).list_items(
            creator_sec_uid="MS4w.test",
            tag="AI",
            keyword="知识",
            limit=5,
        )

        cursor = connection.cursor_instance
        self.assertEqual(len(items), 1)
        self.assertIn("v.creator_sec_uid = %s", cursor.sql)
        self.assertIn("JSON_CONTAINS", cursor.sql)
        self.assertIn("t.transcript_text", cursor.sql)
        self.assertEqual(cursor.params[0:3], ("done", "MS4w.test", "AI"))
        self.assertEqual(cursor.params[-1], 5)
        self.assertEqual(cursor.params.count("%知识%"), 5)

    def test_find_video_can_disambiguate_by_creator(self) -> None:
        connection = FakeConnection([ROW])
        KnowledgeRepository(connection).find_video("7103", "MS4w.test")

        self.assertEqual(
            connection.cursor_instance.params,
            ("done", "7103", "MS4w.test"),
        )


if __name__ == "__main__":
    unittest.main()
