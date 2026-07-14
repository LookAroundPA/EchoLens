"""Application service that maps database rows into frontend API contracts."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from echolens.api.evidence import key_point_evidence, search_match
from echolens.api.models import (
    CreatorDetailResponse,
    CreatorListResponse,
    DashboardResponse,
    SearchHit,
    SearchResponse,
    VideoDetail,
    creator_summary_from_row,
    json_string_list,
    tag_counts,
    transcript_segments,
    video_summary_from_row,
)
from echolens.storage.frontend_repository import FrontendRepository


class FrontendService:
    """Build browser-facing responses without exposing raw database rows."""

    def __init__(self, repository: FrontendRepository) -> None:
        self.repository = repository

    def dashboard(self) -> DashboardResponse:
        counts = self.repository.dashboard_counts()
        status_counts = {
            str(row["status"]): int(row.get("item_count") or 0)
            for row in self.repository.status_counts()
        }
        return DashboardResponse(
            creator_count=int(counts.get("creator_count") or 0),
            video_count=int(counts.get("video_count") or 0),
            completed_count=int(counts.get("completed_count") or 0),
            status_counts=status_counts,
            top_tags=tag_counts(self.repository.completed_tag_rows()),
            recent_videos=[
                video_summary_from_row(row) for row in self.repository.recent_videos(limit=10)
            ],
        )

    def creators(self, query: str | None, limit: int) -> CreatorListResponse:
        rows, total = self.repository.list_creators(query=query, limit=limit)
        tags_by_creator = self._tags_by_creator(self.repository.completed_tag_rows())
        return CreatorListResponse(
            items=[
                creator_summary_from_row(
                    row,
                    top_tags=[tag for tag, _ in tags_by_creator.get(str(row["sec_uid"]), [])[:8]],
                )
                for row in rows
            ],
            total=total,
        )

    def creator_detail(self, sec_uid: str, limit: int) -> CreatorDetailResponse | None:
        creator_row = self.repository.get_creator(sec_uid)
        if creator_row is None:
            return None
        creator_tag_counts = tag_counts(
            self.repository.completed_tag_rows(creator_sec_uid=sec_uid),
            limit=20,
        )
        return CreatorDetailResponse(
            creator=creator_summary_from_row(
                creator_row,
                top_tags=[item.tag for item in creator_tag_counts[:8]],
            ),
            top_tags=creator_tag_counts,
            videos=[
                video_summary_from_row(row)
                for row in self.repository.creator_videos(sec_uid, limit=limit)
            ],
        )

    def search(
        self,
        *,
        query: str,
        creator_sec_uid: str | None,
        tag: str | None,
        limit: int,
    ) -> SearchResponse:
        rows, total = self.repository.search_videos(
            query=query,
            creator_sec_uid=creator_sec_uid,
            tag=tag,
            limit=limit,
        )
        items: list[SearchHit] = []
        for row in rows:
            summary = video_summary_from_row(row)
            items.append(
                SearchHit(
                    **summary.model_dump(),
                    match=search_match(row, query),
                )
            )
        return SearchResponse(items=items, total=total)

    def video_detail(self, video_db_id: int) -> VideoDetail | None:
        row = self.repository.get_video(video_db_id)
        if row is None:
            return None
        summary = video_summary_from_row(row)
        segments = transcript_segments(row.get("segments_json"))
        return VideoDetail(
            **summary.model_dump(),
            transcript=row.get("transcript_text"),
            segments=segments,
            key_point_evidence=key_point_evidence(summary.key_points, segments),
            language=row.get("language"),
            audio_size=(int(row["audio_size"]) if row.get("audio_size") is not None else None),
            audio_url=(f"/api/videos/{video_db_id}/audio" if row.get("audio_path") else None),
            transcription_model=row.get("transcription_model"),
            analysis_model=row.get("analysis_model"),
        )

    @staticmethod
    def _tags_by_creator(
        rows: list[dict[str, Any]],
    ) -> dict[str, list[tuple[str, int]]]:
        counters: dict[str, Counter[str]] = defaultdict(Counter)
        for row in rows:
            counters[str(row["creator_sec_uid"])].update(
                json_string_list(row.get("tags_json"))
            )
        return {
            creator: counter.most_common()
            for creator, counter in counters.items()
        }
