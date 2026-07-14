"""Service for small-scope manual editing and portable exports."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from echolens.api.models import VideoDetail
from echolens.api.service import FrontendService
from echolens.storage.content_repository import ContentRepository
from echolens.storage.frontend_repository import FrontendRepository


class ContentService:
    """Update one video's knowledge content and export the current view."""

    def __init__(
        self,
        writer: ContentRepository,
        reader: FrontendRepository,
    ) -> None:
        self.writer = writer
        self.frontend = FrontendService(reader)

    def update_transcript(self, video_db_id: int, transcript: str) -> VideoDetail | None:
        self.writer.update_transcript(video_db_id, transcript)
        return self.frontend.video_detail(video_db_id)

    def update_analysis(
        self,
        video_db_id: int,
        *,
        summary: str,
        tags: list[str],
        key_points: list[str],
    ) -> VideoDetail | None:
        self.writer.update_analysis(
            video_db_id,
            summary=summary,
            tags=tags,
            key_points=key_points,
        )
        return self.frontend.video_detail(video_db_id)

    def video_detail(self, video_db_id: int) -> VideoDetail | None:
        return self.frontend.video_detail(video_db_id)

    def export_json(self, video: VideoDetail) -> dict[str, Any]:
        payload = video.model_dump(by_alias=True, mode="json")
        payload["analysisStale"] = self.analysis_stale(video)
        payload["exportedAt"] = datetime.now(timezone.utc).isoformat()
        return payload

    def export_markdown(self, video: VideoDetail) -> str:
        title = video.description or f"视频 {video.video_id}"
        analysis_state = "需要重新分析" if self.analysis_stale(video) else "当前"
        tags = "、".join(video.tags) if video.tags else "—"
        evidence_by_point = {
            item.key_point_index: item for item in video.key_point_evidence
        }
        key_point_lines: list[str] = []
        for index, point in enumerate(video.key_points, start=1):
            evidence = evidence_by_point.get(index - 1)
            source = ""
            if evidence is not None:
                source = (
                    f"（来源 {self._format_seconds(evidence.start)}"
                    f"–{self._format_seconds(evidence.end)}）"
                )
            key_point_lines.append(f"{index}. {point}{source}")
        key_points = "\n".join(key_point_lines) or "暂无关键观点。"
        transcript = video.transcript or "暂无转写文本。"
        segments = "\n".join(
            f"- {self._format_seconds(item.start)}–{self._format_seconds(item.end)} {item.text}"
            for item in video.segments
        ) or "暂无时间戳分段。"

        return "\n".join(
            [
                f"# {title}",
                "",
                "## 基础信息",
                "",
                f"- 数据库 ID：{video.id}",
                f"- 平台：{video.platform}",
                f"- 平台视频 ID：{video.video_id}",
                f"- 创作者：{video.creator_name or '未命名创作者'}",
                f"- 创作者 sec_uid：{video.creator_sec_uid}",
                f"- 发布时间：{video.published_at.isoformat() if video.published_at else '—'}",
                f"- 处理状态：{video.status}",
                f"- 分析状态：{analysis_state}",
                f"- 转写模型：{video.transcription_model or '—'}",
                f"- 分析模型：{video.analysis_model or '—'}",
                "",
                "## 摘要",
                "",
                video.summary or "暂无摘要。",
                "",
                "## 标签",
                "",
                tags,
                "",
                "## 关键观点",
                "",
                key_points,
                "",
                "## 完整转写",
                "",
                transcript,
                "",
                "## 时间戳分段",
                "",
                segments,
                "",
            ]
        )

    @staticmethod
    def analysis_stale(video: VideoDetail) -> bool:
        has_analysis = bool(
            video.summary
            or video.tags
            or video.key_points
            or video.analysis_model
        )
        return video.status == "transcribed" and has_analysis

    @staticmethod
    def _format_seconds(value: float) -> str:
        safe = max(0, int(value))
        minutes, seconds = divmod(safe, 60)
        return f"{minutes}:{seconds:02d}"
