from __future__ import annotations

from datetime import datetime
import unittest

from fastapi.testclient import TestClient

from echolens.api.app import create_app
from echolens.api.dependencies import get_knowledge_service, get_operation_service
from echolens.api.models import JobStatus, ProcessingJob
from echolens.api.semantic_models import (
    AskResponse,
    KnowledgeSource,
    SemanticIndexStatusResponse,
    SemanticMatch,
    SemanticSearchHit,
    SemanticSearchResponse,
)
from echolens.core.config import Settings


class FakeKnowledgeService:
    def status(self) -> SemanticIndexStatusResponse:
        return SemanticIndexStatusResponse(
            ready=True,
            model="BAAI/bge-small-zh-v1.5",
            video_count=2,
            chunk_count=7,
            indexed_at=datetime(2026, 7, 14, 12, 0, 0),
            auto_sync=True,
        )

    def search(self, query, creator_sec_uid, tag, limit) -> SemanticSearchResponse:
        return SemanticSearchResponse(
            items=[
                SemanticSearchHit(
                    id=7,
                    platform="douyin",
                    video_id="source-7",
                    creator_sec_uid=creator_sec_uid or "creator-7",
                    creator_name="创作者",
                    description="AI 与效率",
                    summary="摘要",
                    tags=[tag or "AI"],
                    key_points=[],
                    status="done",
                    match=SemanticMatch(
                        source_type="transcript",
                        text="把重复劳动交给人工智能",
                        start=12.0,
                        end=18.0,
                        segment_index=3,
                        segment_count=1,
                        score=0.88,
                        semantic_score=0.84,
                        keyword_score=1.0,
                    ),
                )
            ],
            total=1,
            index=self.status(),
        )

    def ask(self, question, creator_sec_uid, tag, max_sources, thinking) -> AskResponse:
        return AskResponse(
            answer="可以减少重复劳动。[S1]",
            insufficient_evidence=False,
            sources=[
                KnowledgeSource(
                    source_id="S1",
                    video_id=7,
                    platform_video_id="source-7",
                    creator_sec_uid=creator_sec_uid or "creator-7",
                    creator_name="创作者",
                    title="AI 与效率",
                    source_type="transcript",
                    start=12.0,
                    end=18.0,
                    segment_index=3,
                    segment_count=1,
                    text="把重复劳动交给人工智能",
                    score=0.88,
                )
            ],
            model="deepseek-v4-pro",
            thinking=thinking,
        )


class FakeOperationService:
    def create_job(self, job_type, payload, video_id=None) -> ProcessingJob:
        now = datetime(2026, 7, 14, 12, 0, 0)
        return ProcessingJob(
            id=91,
            video_id=video_id,
            job_type=job_type,
            status=JobStatus.queued,
            payload=payload,
            created_at=now,
            updated_at=now,
        )


class SemanticApiRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        app = create_app(Settings(api_cors_origins="http://localhost:5173"))
        app.dependency_overrides[get_knowledge_service] = lambda: FakeKnowledgeService()
        app.dependency_overrides[get_operation_service] = lambda: FakeOperationService()
        self.client = TestClient(app)

    def test_status_and_hybrid_search_contract(self) -> None:
        status = self.client.get("/api/semantic/status")
        search = self.client.get(
            "/api/semantic/search",
            params={"q": "提高效率", "creator": "creator-7", "tag": "AI"},
        )

        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json()["chunkCount"], 7)
        self.assertEqual(search.status_code, 200)
        self.assertEqual(search.json()["items"][0]["match"]["sourceType"], "transcript")
        self.assertEqual(search.json()["items"][0]["match"]["segmentIndex"], 3)

    def test_sync_is_queued_and_qa_keeps_clickable_sources(self) -> None:
        sync = self.client.post("/api/semantic/actions/sync", json={"rebuild": True})
        answer = self.client.post(
            "/api/ask",
            json={
                "question": "怎样提高效率？",
                "creatorSecUid": "creator-7",
                "maxSources": 8,
                "thinking": True,
            },
        )

        self.assertEqual(sync.status_code, 202)
        self.assertEqual(sync.json()["jobType"], "semantic_index")
        self.assertTrue(sync.json()["payload"]["rebuild"])
        self.assertEqual(answer.status_code, 200)
        self.assertEqual(answer.json()["model"], "deepseek-v4-pro")
        self.assertTrue(answer.json()["thinking"])
        self.assertEqual(answer.json()["sources"][0]["videoId"], 7)
        self.assertEqual(answer.json()["sources"][0]["start"], 12.0)
        self.assertIn("[S1]", answer.json()["answer"])


if __name__ == "__main__":
    unittest.main()
