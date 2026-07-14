from __future__ import annotations

from datetime import datetime
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from echolens.api.content_routes import router
from echolens.api.dependencies import get_content_service
from echolens.api.models import TranscriptSegment, VideoDetail


def make_video(*, status: str = "done") -> VideoDetail:
    return VideoDetail(
        id=7,
        platform="douyin",
        video_id="source-7",
        creator_sec_uid="sec-user-7",
        creator_name="测试创作者",
        description="测试视频",
        summary="旧摘要",
        tags=["旧标签"],
        key_points=["旧观点"],
        published_at=None,
        status=status,
        updated_at=datetime(2026, 7, 14, 12, 0, 0),
        transcript="旧转写",
        segments=[TranscriptSegment(start=0, end=3, text="旧转写")],
        language="zh",
        audio_size=None,
        audio_url=None,
        transcription_model="large-v3",
        analysis_model="deepseek-test",
    )


class FakeContentService:
    def __init__(self) -> None:
        self.video = make_video()
        self.transcript: str | None = None
        self.analysis: tuple[str, list[str], list[str]] | None = None

    def update_transcript(self, video_db_id: int, transcript: str) -> VideoDetail:
        assert video_db_id == 7
        self.transcript = transcript
        self.video = self.video.model_copy(
            update={"transcript": transcript, "status": "transcribed"}
        )
        return self.video

    def update_analysis(
        self,
        video_db_id: int,
        *,
        summary: str,
        tags: list[str],
        key_points: list[str],
    ) -> VideoDetail:
        assert video_db_id == 7
        self.analysis = (summary, tags, key_points)
        self.video = self.video.model_copy(
            update={
                "summary": summary,
                "tags": tags,
                "key_points": key_points,
                "status": "done",
            }
        )
        return self.video

    def video_detail(self, video_db_id: int) -> VideoDetail | None:
        return self.video if video_db_id == 7 else None

    def export_markdown(self, video: VideoDetail) -> str:
        return f"# {video.description}\n\n{video.transcript}\n"

    def export_json(self, video: VideoDetail) -> dict[str, object]:
        return {"id": video.id, "transcript": video.transcript}


class ContentRoutesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = FakeContentService()
        app = FastAPI()
        app.include_router(router, prefix="/api")
        app.dependency_overrides[get_content_service] = lambda: self.service
        self.client = TestClient(app)

    def test_updates_transcript_and_marks_analysis_stale(self) -> None:
        response = self.client.patch(
            "/api/videos/7/transcript",
            json={"transcript": "  人工修正后的转写  "},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.service.transcript, "人工修正后的转写")
        self.assertEqual(response.json()["status"], "transcribed")
        self.assertEqual(response.json()["transcript"], "人工修正后的转写")

    def test_rejects_empty_transcript(self) -> None:
        response = self.client.patch(
            "/api/videos/7/transcript",
            json={"transcript": "   "},
        )

        self.assertEqual(response.status_code, 422)
        self.assertIsNone(self.service.transcript)

    def test_normalizes_analysis_lists(self) -> None:
        response = self.client.patch(
            "/api/videos/7/analysis",
            json={
                "summary": "  新摘要  ",
                "tags": [" AI ", "", "AI", "学习"],
                "keyPoints": [" 观点一 ", "观点一", "观点二"],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.service.analysis,
            ("新摘要", ["AI", "学习"], ["观点一", "观点二"]),
        )
        self.assertEqual(response.json()["status"], "done")

    def test_exports_markdown_and_json_with_safe_names(self) -> None:
        markdown = self.client.get("/api/videos/7/export/markdown")
        exported_json = self.client.get("/api/videos/7/export/json")

        self.assertEqual(markdown.status_code, 200)
        self.assertIn("echolens-video-7.md", markdown.headers["content-disposition"])
        self.assertIn("测试视频", markdown.text)
        self.assertEqual(exported_json.status_code, 200)
        self.assertIn("echolens-video-7.json", exported_json.headers["content-disposition"])
        self.assertEqual(exported_json.json()["id"], 7)


if __name__ == "__main__":
    unittest.main()
