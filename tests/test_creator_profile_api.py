from __future__ import annotations

from fastapi.testclient import TestClient

from echolens.api.app import create_app
from echolens.api.creator_profile import (
    CreatorInsight,
    CreatorPointSource,
    CreatorProfile,
    CreatorProfileResponse,
    RepresentativeVideo,
)
from echolens.api.dependencies import get_frontend_service
from echolens.api.models import CreatorSummary, TagCount
from echolens.core.config import Settings


class FakeCreatorProfileService:
    def creator_detail(self, sec_uid: str, limit: int):
        if sec_uid == "missing":
            return None
        representative = RepresentativeVideo(
            id=7,
            platform="douyin",
            video_id="source-7",
            creator_sec_uid=sec_uid,
            creator_name="创作者",
            description="代表视频",
            summary="视频摘要",
            tags=["AI"],
            key_points=["人工智能减少重复劳动"],
            status="done",
            reason="覆盖 AI；包含 1 条关键观点",
        )
        return CreatorProfileResponse(
            creator=CreatorSummary(
                platform="douyin",
                sec_uid=sec_uid,
                name="创作者",
                video_count=1,
                completed_count=1,
            ),
            top_tags=[TagCount(tag="AI", count=1)],
            videos=[representative],
            profile=CreatorProfile(
                overview="创作者当前已沉淀 1 条完成内容。",
                analyzed_video_count=1,
                main_themes=[TagCount(tag="AI", count=1)],
                insights=[
                    CreatorInsight(
                        text="人工智能减少重复劳动",
                        occurrence_count=1,
                        sources=[
                            CreatorPointSource(
                                video_id=7,
                                title="代表视频",
                                start=12.0,
                                end=18.0,
                                segment_index=3,
                                excerpt="人工智能可以减少重复劳动",
                            )
                        ],
                    )
                ],
                representative_videos=[representative],
                recent_videos=[representative],
            ),
        )


def test_creator_profile_endpoint_returns_playable_sources() -> None:
    app = create_app(Settings(api_cors_origins="http://localhost:5173"))
    app.dependency_overrides[get_frontend_service] = lambda: FakeCreatorProfileService()
    client = TestClient(app)

    response = client.get("/api/creators/creator-1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["profile"]["analyzedVideoCount"] == 1
    assert payload["profile"]["mainThemes"][0] == {"tag": "AI", "count": 1}
    assert payload["profile"]["insights"][0]["sources"][0] == {
        "videoId": 7,
        "title": "代表视频",
        "publishedAt": None,
        "start": 12.0,
        "end": 18.0,
        "segmentIndex": 3,
        "excerpt": "人工智能可以减少重复劳动",
    }


def test_missing_creator_profile_returns_not_found() -> None:
    app = create_app(Settings(api_cors_origins="http://localhost:5173"))
    app.dependency_overrides[get_frontend_service] = lambda: FakeCreatorProfileService()
    client = TestClient(app)

    response = client.get("/api/creators/missing")

    assert response.status_code == 404
