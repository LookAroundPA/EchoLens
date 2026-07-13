"""Frontend catalog service for videos and tags."""

from echolens.api.models import TagListResponse, VideoListResponse, tag_counts, video_summary_from_row
from echolens.storage.management_repository import ManagementRepository


class ManagementService:
    """Build browser-facing catalog responses for operational pages."""

    def __init__(self, repository: ManagementRepository) -> None:
        self.repository = repository

    def videos(
        self,
        *,
        query: str | None,
        creator_sec_uid: str | None,
        status: str | None,
        tag: str | None,
        limit: int,
        offset: int,
    ) -> VideoListResponse:
        rows, total = self.repository.list_videos(
            query=query,
            creator_sec_uid=creator_sec_uid,
            status=status,
            tag=tag,
            limit=limit,
            offset=offset,
        )
        return VideoListResponse(
            items=[video_summary_from_row(row) for row in rows],
            total=total,
        )

    def tags(self, *, creator_sec_uid: str | None, limit: int) -> TagListResponse:
        return TagListResponse(
            items=tag_counts(self.repository.tag_rows(creator_sec_uid), limit=limit)
        )
