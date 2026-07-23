"""Tests for invalidating normalized opinions when source content changes."""

import unittest

from echolens.intelligence.repository import IntelligenceRepository


class RecordingIntelligenceRepository(IntelligenceRepository):
    def __init__(self, *, context=True, opinions=None) -> None:
        self.context = {"analysis_id": 17} if context else None
        self.opinions = opinions or []
        self.deleted_ids: list[int] = []
        self.rebuilt_pairs: list[tuple[int, int]] = []
        self.cleanup_calls = 0

    def _get_analysis_context(self, video_db_id):
        self.video_db_id = video_db_id
        return self.context

    def _get_existing_opinions(self, analysis_id):
        self.analysis_id = analysis_id
        return self.opinions

    def _delete_stale_opinions(self, opinion_ids):
        self.deleted_ids = list(opinion_ids)

    def rebuild_change_history(self, creator_id, topic_id):
        self.rebuilt_pairs.append((creator_id, topic_id))

    def remove_unreferenced_pending_topics(self):
        self.cleanup_calls += 1
        return 0


class IntelligenceRepositoryInvalidationTests(unittest.TestCase):
    def test_removes_video_opinions_and_rebuilds_each_affected_history(self) -> None:
        repository = RecordingIntelligenceRepository(
            opinions=[
                {"id": 3, "creator_id": 8, "topic_id": 21, "insight_index": 0},
                {"id": 4, "creator_id": 8, "topic_id": 22, "insight_index": 1},
                {"id": 5, "creator_id": 8, "topic_id": 21, "insight_index": 2},
            ]
        )

        removed = repository.remove_video_analysis(99)

        self.assertEqual(removed, 3)
        self.assertEqual(repository.video_db_id, 99)
        self.assertEqual(repository.analysis_id, 17)
        self.assertEqual(repository.deleted_ids, [3, 4, 5])
        self.assertEqual(repository.rebuilt_pairs, [(8, 21), (8, 22)])
        self.assertEqual(repository.cleanup_calls, 1)

    def test_missing_analysis_or_opinions_is_a_noop(self) -> None:
        missing_analysis = RecordingIntelligenceRepository(context=False)
        missing_opinions = RecordingIntelligenceRepository(context=True, opinions=[])

        self.assertEqual(missing_analysis.remove_video_analysis(7), 0)
        self.assertEqual(missing_opinions.remove_video_analysis(7), 0)
        self.assertEqual(missing_analysis.cleanup_calls, 0)
        self.assertEqual(missing_opinions.cleanup_calls, 0)


if __name__ == "__main__":
    unittest.main()
