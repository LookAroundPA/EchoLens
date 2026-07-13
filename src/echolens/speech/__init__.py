"""Speech recognition services."""

from echolens.speech.faster_whisper import (
    FasterWhisperTranscriber,
    TranscriptSegment,
    TranscriptionResult,
)

__all__ = [
    "FasterWhisperTranscriber",
    "TranscriptSegment",
    "TranscriptionResult",
]
