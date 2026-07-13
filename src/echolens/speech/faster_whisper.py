"""Faster-Whisper backed local transcription."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from echolens.core.config import Settings, get_settings


@dataclass(frozen=True)
class TranscriptSegment:
    """One timestamped transcript segment."""

    start: float
    end: float
    text: str

    def as_dict(self) -> dict[str, float | str]:
        """Return a JSON-serializable representation."""

        return {
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "text": self.text,
        }


@dataclass(frozen=True)
class TranscriptionResult:
    """Normalized transcription output persisted by EchoLens."""

    text: str
    segments: list[TranscriptSegment]
    language: str | None
    model_name: str


class FasterWhisperTranscriber:
    """Load one Faster-Whisper model and reuse it across audio files."""

    def __init__(self, settings: Settings | None = None, model: Any | None = None) -> None:
        self.settings = settings or get_settings()
        self._model = model

    def _get_model(self) -> Any:
        if self._model is None:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                self.settings.whisper_model,
                device=self.settings.whisper_device,
                compute_type=self.settings.whisper_compute_type,
            )
        return self._model

    def transcribe(self, audio_path: Path) -> TranscriptionResult:
        """Transcribe one audio file and fully materialize all segments."""

        if not audio_path.is_file():
            raise FileNotFoundError(f"Audio file does not exist: {audio_path}")

        model = self._get_model()
        raw_segments, info = model.transcribe(
            str(audio_path),
            beam_size=self.settings.whisper_beam_size,
            language=self.settings.whisper_language or None,
            vad_filter=self.settings.whisper_vad_filter,
        )

        segments: list[TranscriptSegment] = []
        transcript_parts: list[str] = []
        for segment in raw_segments:
            raw_text = str(segment.text)
            transcript_parts.append(raw_text)
            segments.append(
                TranscriptSegment(
                    start=float(segment.start),
                    end=float(segment.end),
                    text=raw_text.strip(),
                )
            )
        transcript_text = "".join(transcript_parts).strip()

        return TranscriptionResult(
            text=transcript_text,
            segments=segments,
            language=getattr(info, "language", None),
            model_name=self.settings.whisper_model,
        )
