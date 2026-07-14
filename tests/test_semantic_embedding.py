from __future__ import annotations

from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import ModuleType
import unittest

from echolens.core.config import Settings
from echolens.semantic.embedding import FastEmbedder


class FakeTextEmbedding:
    calls: list[dict] = []

    def __init__(self, **kwargs) -> None:
        self.calls.append(kwargs)

    def embed(self, texts):
        for _text in texts:
            yield [3.0, 4.0]


class SemanticEmbeddingTests(unittest.TestCase):
    def test_model_uses_configured_cache_and_normalizes_vectors(self) -> None:
        fake_module = ModuleType("fastembed")
        fake_module.TextEmbedding = FakeTextEmbedding
        previous = sys.modules.get("fastembed")
        sys.modules["fastembed"] = fake_module
        FakeTextEmbedding.calls.clear()
        try:
            with TemporaryDirectory() as temporary:
                cache_dir = Path(temporary) / "fastembed"
                settings = Settings(
                    semantic_model="fake-model",
                    semantic_model_cache_dir=cache_dir,
                )
                embedder = FastEmbedder(settings)

                vector = embedder.embed_query("测试问题")

                self.assertEqual(vector, (0.6, 0.8))
                self.assertEqual(
                    FakeTextEmbedding.calls,
                    [
                        {
                            "model_name": "fake-model",
                            "cache_dir": str(cache_dir),
                        }
                    ],
                )
        finally:
            if previous is None:
                sys.modules.pop("fastembed", None)
            else:
                sys.modules["fastembed"] = previous


if __name__ == "__main__":
    unittest.main()
