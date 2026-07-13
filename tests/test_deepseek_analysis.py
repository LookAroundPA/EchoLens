"""Tests for DeepSeek structured content analysis."""

import json
from types import SimpleNamespace
import unittest

from echolens.analysis.deepseek import DeepSeekAnalyzer
from echolens.core.config import Settings


class FakeCompletions:
    def __init__(self, content: str, finish_reason: str = "stop") -> None:
        self.content = content
        self.finish_reason = finish_reason
        self.request: dict[str, object] | None = None

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.request = kwargs
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason=self.finish_reason,
                    message=SimpleNamespace(content=self.content),
                )
            ]
        )


class DeepSeekAnalyzerTests(unittest.TestCase):
    def test_parses_and_normalizes_structured_json(self) -> None:
        completions = FakeCompletions(
            json.dumps(
                {
                    "summary": "  这是摘要  ",
                    "tags": ["AI", "AI", " 技术 "],
                    "key_points": ["观点一", "观点二"],
                },
                ensure_ascii=False,
            )
        )
        client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
        settings = Settings(
            llm_api_key="test-key",
            llm_model="deepseek-v4-flash",
        )

        result = DeepSeekAnalyzer(settings, client=client).analyze("转写内容", "视频描述")

        self.assertEqual(result.summary, "这是摘要")
        self.assertEqual(result.tags, ["AI", "技术"])
        self.assertEqual(result.key_points, ["观点一", "观点二"])
        assert completions.request is not None
        self.assertEqual(completions.request["response_format"], {"type": "json_object"})
        self.assertEqual(
            completions.request["extra_body"],
            {"thinking": {"type": "disabled"}},
        )

    def test_rejects_empty_transcript(self) -> None:
        settings = Settings(llm_api_key="test-key")
        with self.assertRaisesRegex(ValueError, "Transcript text is empty"):
            DeepSeekAnalyzer(settings, client=object()).analyze("   ")

    def test_rejects_truncated_response(self) -> None:
        completions = FakeCompletions("{}", finish_reason="length")
        client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
        settings = Settings(llm_api_key="test-key")

        with self.assertRaisesRegex(ValueError, "truncated"):
            DeepSeekAnalyzer(settings, client=client).analyze("转写内容")


if __name__ == "__main__":
    unittest.main()
