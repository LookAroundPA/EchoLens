from __future__ import annotations

import json
from types import SimpleNamespace
import unittest

from echolens.api.semantic_models import KnowledgeSource
from echolens.core.config import Settings
from echolens.semantic.qa import DeepSeekKnowledgeAnswerer


class FakeCompletions:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.requests: list[dict] = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(content=json.dumps(self.payload, ensure_ascii=False)),
                )
            ]
        )


class FakeClient:
    def __init__(self, payload: dict) -> None:
        self.completions = FakeCompletions(payload)
        self.chat = SimpleNamespace(completions=self.completions)


def source(source_id: str = "S1") -> KnowledgeSource:
    return KnowledgeSource(
        source_id=source_id,
        video_id=7,
        platform_video_id="video-7",
        creator_sec_uid="creator-7",
        creator_name="创作者",
        title="AI 与工作效率",
        source_type="transcript",
        start=12.0,
        end=18.0,
        segment_index=3,
        segment_count=1,
        text="把重复劳动交给人工智能，人应该专注判断和创造。",
        score=0.88,
    )


class SemanticQaTests(unittest.TestCase):
    def test_standard_mode_disables_thinking_and_keeps_json_citations(self) -> None:
        client = FakeClient(
            {
                "answer": "可以把重复劳动交给人工智能。[S1]",
                "insufficient_evidence": False,
                "used_source_ids": ["S1", "S99"],
            }
        )
        settings = Settings(
            llm_api_key="test-key",
            qa_model="deepseek-v4-pro",
            qa_temperature=0.1,
        )
        answerer = DeepSeekKnowledgeAnswerer(settings, client=client)

        result = answerer.answer("怎样提高效率？", [source()], thinking=False)
        request = client.completions.requests[0]

        self.assertEqual(result.used_source_ids, ["S1"])
        self.assertIn("[S1]", result.answer)
        self.assertEqual(request["model"], "deepseek-v4-pro")
        self.assertEqual(request["extra_body"], {"thinking": {"type": "disabled"}})
        self.assertEqual(request["temperature"], 0.1)
        self.assertNotIn("reasoning_effort", request)
        self.assertEqual(request["response_format"], {"type": "json_object"})

    def test_deep_mode_enables_high_effort_without_temperature(self) -> None:
        client = FakeClient(
            {
                "answer": "现有来源支持这一结论。[S1]",
                "insufficient_evidence": False,
                "used_source_ids": ["S1"],
            }
        )
        answerer = DeepSeekKnowledgeAnswerer(
            Settings(llm_api_key="test-key", qa_model="deepseek-v4-pro"),
            client=client,
        )

        answerer.answer("比较不同观点", [source()], thinking=True)
        request = client.completions.requests[0]

        self.assertEqual(request["extra_body"], {"thinking": {"type": "enabled"}})
        self.assertEqual(request["reasoning_effort"], "high")
        self.assertNotIn("temperature", request)

    def test_no_sources_refuses_without_calling_deepseek(self) -> None:
        client = FakeClient({})
        answerer = DeepSeekKnowledgeAnswerer(
            Settings(llm_api_key="test-key"),
            client=client,
        )

        result = answerer.answer("没有证据的问题", [], thinking=False)

        self.assertTrue(result.insufficient_evidence)
        self.assertEqual(client.completions.requests, [])


if __name__ == "__main__":
    unittest.main()
