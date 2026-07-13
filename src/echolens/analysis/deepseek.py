"""DeepSeek-backed transcript analysis."""

import json
from typing import Any

from echolens.analysis.models import AnalysisResult
from echolens.core.config import Settings, get_settings


SYSTEM_PROMPT = """你是 EchoLens 的内容分析器。请根据用户提供的视频转写文本，输出严格 JSON，不要输出 Markdown 或额外说明。

JSON 必须包含：
{
  "summary": "一段简洁但完整的中文摘要",
  "tags": ["3 到 8 个简短中文主题标签"],
  "key_points": ["3 到 10 条关键观点或事实"]
}

只根据转写内容总结，不要补充文本中没有的信息。"""


class DeepSeekAnalyzer:
    """Call the OpenAI-compatible DeepSeek Chat Completions API."""

    def __init__(self, settings: Settings | None = None, client: Any | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = client

    def _get_client(self) -> Any:
        if self._client is None:
            if not self.settings.llm_api_key:
                raise ValueError("LLM_API_KEY is required for DeepSeek analysis")

            from openai import OpenAI

            self._client = OpenAI(
                api_key=self.settings.llm_api_key,
                base_url=self.settings.llm_base_url,
            )
        return self._client

    def analyze(self, transcript_text: str, description: str | None = None) -> AnalysisResult:
        """Analyze one transcript and return validated structured content."""

        transcript = transcript_text.strip()
        if not transcript:
            raise ValueError("Transcript text is empty")

        context: list[str] = []
        if description and description.strip():
            context.append(f"视频描述：{description.strip()}")
        context.append(f"转写文本：\n{transcript}")

        response = self._get_client().chat.completions.create(
            model=self.settings.llm_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": "\n\n".join(context)},
            ],
            response_format={"type": "json_object"},
            temperature=self.settings.llm_temperature,
            max_tokens=self.settings.llm_max_tokens,
            stream=False,
            extra_body={"thinking": {"type": "disabled"}},
        )

        choice = response.choices[0]
        if getattr(choice, "finish_reason", None) == "length":
            raise ValueError("DeepSeek response was truncated by max_tokens")

        content = choice.message.content
        if not content or not content.strip():
            raise ValueError("DeepSeek returned empty content")
        return AnalysisResult.model_validate(json.loads(content))
