"""Grounded cross-video answers generated with DeepSeek V4 Pro."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from echolens.api.semantic_models import KnowledgeSource
from echolens.core.config import Settings, get_settings


SYSTEM_PROMPT = """你是 EchoLens 的本地知识问答助手。
你只能依据用户提供的来源片段回答，不得使用来源之外的事实补全答案。

要求：
1. 每个实质性结论后必须使用 [S1]、[S2] 这样的来源标记。
2. 只能引用实际提供的来源编号。
3. 来源不足时明确说明，不要猜测，并将 insufficient_evidence 设为 true。
4. 可以综合多个视频，但要区分不同创作者或不同观点。
5. 输出严格 JSON，不要输出 Markdown 代码块或额外说明。

JSON 格式：
{
  "answer": "带 [S1] 引用标记的中文回答",
  "insufficient_evidence": false,
  "used_source_ids": ["S1", "S2"]
}
"""


class GeneratedAnswer(BaseModel):
    answer: str
    insufficient_evidence: bool = False
    used_source_ids: list[str] = Field(default_factory=list)


class DeepSeekKnowledgeAnswerer:
    """Ask DeepSeek to synthesize an answer only from retrieved local sources."""

    def __init__(self, settings: Settings | None = None, client: Any | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = client

    def answer(
        self,
        question: str,
        sources: list[KnowledgeSource],
        *,
        thinking: bool,
    ) -> GeneratedAnswer:
        if not sources:
            return GeneratedAnswer(
                answer="当前知识库没有检索到足够相关的内容，无法基于视频证据回答这个问题。",
                insufficient_evidence=True,
            )

        source_blocks = []
        for source in sources:
            location = ""
            if source.start is not None:
                location = f"，时间 {source.start:.2f}-{(source.end or source.start):.2f} 秒"
            source_blocks.append(
                "\n".join(
                    [
                        f"[{source.source_id}] 创作者：{source.creator_name or source.creator_sec_uid}",
                        f"视频：{source.title}{location}",
                        f"内容：{source.text}",
                    ]
                )
            )

        request: dict[str, Any] = {
            "model": self.settings.qa_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"问题：{question.strip()}\n\n"
                        "可用来源：\n\n"
                        + "\n\n".join(source_blocks)
                    ),
                },
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": self.settings.qa_max_tokens,
            "stream": False,
            "extra_body": {
                "thinking": {"type": "enabled" if thinking else "disabled"}
            },
        }
        if thinking:
            request["reasoning_effort"] = "high"
        else:
            request["temperature"] = self.settings.qa_temperature

        response = self._get_client().chat.completions.create(**request)
        choice = response.choices[0]
        if getattr(choice, "finish_reason", None) == "length":
            raise ValueError("DeepSeek answer was truncated by max_tokens")
        content = choice.message.content
        if not content or not content.strip():
            raise ValueError("DeepSeek returned an empty knowledge answer")

        generated = GeneratedAnswer.model_validate(json.loads(content))
        valid_ids = {source.source_id for source in sources}
        generated.used_source_ids = [
            source_id for source_id in generated.used_source_ids if source_id in valid_ids
        ]
        if not generated.answer.strip():
            raise ValueError("DeepSeek returned an empty answer field")
        return generated

    def _get_client(self) -> Any:
        if self._client is None:
            if not self.settings.llm_api_key:
                raise ValueError("LLM_API_KEY is required for DeepSeek knowledge answering")
            from openai import OpenAI

            self._client = OpenAI(
                api_key=self.settings.llm_api_key,
                base_url=self.settings.llm_base_url,
            )
        return self._client
