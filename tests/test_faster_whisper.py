"""Tests for Faster-Whisper result normalization."""

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from echolens.core.config import Settings
from echolens.speech.faster_whisper import FasterWhisperTranscriber


class FakeModel:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def transcribe(self, audio_path: str, **kwargs: object):
        self.calls.append((audio_path, kwargs))
        segments = iter(
            [
                SimpleNamespace(start=0.0, end=1.25, text=" 你好"),
                SimpleNamespace(start=1.25, end=2.5, text=" 世界 "),
            ]
        )
        return segments, SimpleNamespace(language="zh")


class FasterWhisperTranscriberTests(unittest.TestCase):
    def test_normalizes_text_segments_and_options(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            audio_path = Path(temporary_directory) / "sample.wav"
            audio_path.write_bytes(b"RIFF" + b"0" * 64)
            model = FakeModel()
            settings = Settings(
                whisper_model="large-v3",
                whisper_device="cpu",
                whisper_compute_type="int8",
                whisper_language="",
                whisper_beam_size=3,
                whisper_vad_filter=True,
            )

            result = FasterWhisperTranscriber(settings=settings, model=model).transcribe(audio_path)

            self.assertEqual(result.text, "你好 世界")
            self.assertEqual(result.language, "zh")
            self.assertEqual(result.model_name, "large-v3")
            self.assertEqual(
                [segment.as_dict() for segment in result.segments],
                [
                    {"start": 0.0, "end": 1.25, "text": "你好"},
                    {"start": 1.25, "end": 2.5, "text": "世界"},
                ],
            )
            self.assertEqual(
                model.calls,
                [
                    (
                        str(audio_path),
                        {
                            "beam_size": 3,
                            "language": None,
                            "vad_filter": True,
                        },
                    )
                ],
            )

    def test_rejects_missing_audio_file(self) -> None:
        model = FakeModel()
        transcriber = FasterWhisperTranscriber(settings=Settings(), model=model)

        with self.assertRaises(FileNotFoundError):
            transcriber.transcribe(Path("missing.wav"))

        self.assertEqual(model.calls, [])


if __name__ == "__main__":
    unittest.main()
