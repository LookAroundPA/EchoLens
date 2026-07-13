"""Human-readable and machine-readable knowledge output."""

from __future__ import annotations

import json
from collections.abc import Sequence

from pydantic import BaseModel

from echolens.knowledge.models import CreatorKnowledgeSummary, KnowledgeItem


def render_json(value: BaseModel | Sequence[BaseModel]) -> str:
    """Render Pydantic models as UTF-8 JSON."""

    if isinstance(value, BaseModel):
        payload: object = value.model_dump(mode="json")
    else:
        payload = [item.model_dump(mode="json") for item in value]
    return json.dumps(payload, ensure_ascii=False, indent=2)


def render_creators_text(creators: Sequence[CreatorKnowledgeSummary]) -> str:
    if not creators:
        return "No creators found."
    return "\n".join(
        (
            f"{item.creator_name or '-'} | {item.platform} | {item.sec_uid} "
            f"| done={item.done_count} total={item.video_count}"
        )
        for item in creators
    )


def render_items_text(items: Sequence[KnowledgeItem]) -> str:
    if not items:
        return "No knowledge items found."

    blocks: list[str] = []
    for item in items:
        title = item.creator_name or item.creator_sec_uid
        tags = ", ".join(item.tags) if item.tags else "-"
        blocks.append(
            "\n".join(
                [
                    f"[{item.video_id}] {title}",
                    f"tags: {tags}",
                    f"summary: {item.summary or '-'}",
                ]
            )
        )
    return "\n\n".join(blocks)


def render_items_markdown(items: Sequence[KnowledgeItem]) -> str:
    if not items:
        return "No knowledge items found."

    sections: list[str] = []
    for item in items:
        title = item.creator_name or item.creator_sec_uid
        tags = "、".join(item.tags) if item.tags else "无"
        sections.append(
            "\n".join(
                [
                    f"## {title} · {item.video_id}",
                    "",
                    f"- 创作者 ID：`{item.creator_sec_uid}`",
                    f"- 标签：{tags}",
                    f"- 模型：`{item.analysis_model or '-'}`",
                    "",
                    item.summary or "暂无摘要。",
                ]
            )
        )
    return "\n\n".join(sections)


def render_item_markdown(item: KnowledgeItem) -> str:
    """Render one complete knowledge item as Markdown."""

    title = item.creator_name or item.creator_sec_uid
    tags = "、".join(item.tags) if item.tags else "无"
    key_points = (
        "\n".join(f"- {point}" for point in item.key_points)
        if item.key_points
        else "- 暂无"
    )

    return "\n".join(
        [
            f"# {title} · {item.video_id}",
            "",
            "## 基本信息",
            "",
            f"- 平台：`{item.platform}`",
            f"- 创作者 ID：`{item.creator_sec_uid}`",
            f"- 状态：`{item.status}`",
            f"- 识别语言：`{item.language or '-'}`",
            f"- 分析模型：`{item.analysis_model or '-'}`",
            f"- 标签：{tags}",
            "",
            "## 视频描述",
            "",
            item.description or "无。",
            "",
            "## 摘要",
            "",
            item.summary or "暂无摘要。",
            "",
            "## 关键观点",
            "",
            key_points,
            "",
            "## 完整转写",
            "",
            item.transcript_text or "暂无转写。",
        ]
    )
