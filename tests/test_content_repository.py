"""Tests for manual content edits that affect normalized intelligence."""

import unittest
from unittest.mock import patch

from echolens.storage.content_repository import ContentRepository


class FakeCursor:
    def __init__(self) -> None:
        self.fetchone_values = iter([{"id": 7}, {"id": 11}])
        self.executed: list[tuple[str, tuple[object, ...]]] = []
        self.closed = False

    def execute(self, sql, params=()):
        self.executed.append((" ".join(sql.split()), tuple(params)))

    def fetchone(self):
        return next(self.fetchone_values)

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor=None) -> None:
        self.cursor_instance = cursor or FakeCursor()
        self.commit_calls = 0
        self.rollback_calls = 0

    def cursor(self, **kwargs):
        return self.cursor_instance

    def commit(self):
        self.commit_calls += 1

    def rollback(self):
        self.rollback_calls += 1


class FakeIntelligenceRepository:
    def __init__(self, connection) -> None:
        self.connection = connection
        self.video_ids: list[int] = []

    def remove_video_analysis(self, video_db_id: int) -> int:
        self.video_ids.append(video_db_id)
        return 2


class FakeAnalysisCursor(FakeCursor):
    def __init__(self, *, video_status: str) -> None:
        super().__init__()
        self.fetchone_values = iter([
            {"id": 7, "status": video_status},
            {"id": 11},
            {"id": 13},
        ])


class ContentRepositoryTests(unittest.TestCase):
    def test_transcript_edit_invalidates_normalized_market_opinions(self) -> None:
        connection = FakeConnection()
        intelligence = FakeIntelligenceRepository(connection)

        with patch(
            "echolens.storage.content_repository.IntelligenceRepository",
            return_value=intelligence,
        ):
            ContentRepository(connection).update_transcript(7, "修正后的转写")

        self.assertEqual(intelligence.video_ids, [7])
        self.assertEqual(connection.commit_calls, 1)
        self.assertEqual(connection.rollback_calls, 0)
        self.assertTrue(connection.cursor_instance.closed)
        sql = [statement for statement, _ in connection.cursor_instance.executed]
        self.assertTrue(any("UPDATE transcripts" in statement for statement in sql))
        self.assertTrue(
            any("SET status = 'transcribed'" in statement for statement in sql)
        )

    def test_manual_analysis_after_transcript_change_clears_old_market_insights(self) -> None:
        connection = FakeConnection(FakeAnalysisCursor(video_status="transcribed"))
        intelligence = FakeIntelligenceRepository(connection)

        with patch(
            "echolens.storage.content_repository.IntelligenceRepository",
            return_value=intelligence,
        ):
            ContentRepository(connection).update_analysis(
                7,
                summary="人工摘要",
                tags=["人工"],
                key_points=["人工观点"],
            )

        self.assertEqual(intelligence.video_ids, [7])
        sql = [statement for statement, _ in connection.cursor_instance.executed]
        self.assertTrue(
            any(
                "UPDATE analyses" in statement
                and "market_insights_json = %s" in statement
                and "model_name = 'manual'" in statement
                for statement in sql
            )
        )
        self.assertTrue(any("SET status = 'done'" in statement for statement in sql))
        self.assertEqual(connection.commit_calls, 1)

    def test_manual_edit_of_current_analysis_preserves_market_insights(self) -> None:
        connection = FakeConnection(FakeAnalysisCursor(video_status="done"))
        intelligence = FakeIntelligenceRepository(connection)

        with patch(
            "echolens.storage.content_repository.IntelligenceRepository",
            return_value=intelligence,
        ):
            ContentRepository(connection).update_analysis(
                7,
                summary="修订摘要",
                tags=["修订"],
                key_points=["修订观点"],
            )

        self.assertEqual(intelligence.video_ids, [])
        analysis_updates = [
            statement
            for statement, _ in connection.cursor_instance.executed
            if "UPDATE analyses" in statement
        ]
        self.assertEqual(len(analysis_updates), 1)
        self.assertNotIn("market_insights_json", analysis_updates[0])


if __name__ == "__main__":
    unittest.main()
