"""Minimal database-driven worker for Faster-Whisper transcription."""

from dataclasses import dataclass
from pathlib import Path

from echolens.core.config import Settings, get_settings
from echolens.speech.faster_whisper import FasterWhisperTranscriber
from echolens.storage.mysql import mysql_connection
from echolens.storage.transcript_repository import TranscriptRepository


@dataclass(frozen=True)
class TranscriptionWorkerResult:
    """Result of processing at most one database row."""

    handled: bool
    completed: bool
    failed: bool
    video_db_id: int | None = None
    error_message: str | None = None


class TranscriptionWorker:
    """Advance videos from audio_done to transcribed."""

    def __init__(
        self,
        settings: Settings | None = None,
        transcriber: FasterWhisperTranscriber | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.transcriber = transcriber or FasterWhisperTranscriber(self.settings)

    def process_one(self) -> TranscriptionWorkerResult:
        """Claim and transcribe at most one audio-complete video."""

        with mysql_connection(self.settings) as connection:
            repository = TranscriptRepository(connection)
            video = repository.claim_next_video()
            connection.commit()

        if video is None:
            return TranscriptionWorkerResult(
                handled=False,
                completed=False,
                failed=False,
            )

        video_db_id = int(video["id"])
        try:
            result = self.transcriber.transcribe(Path(str(video["audio_path"])))
            with mysql_connection(self.settings) as connection:
                TranscriptRepository(connection).save_result(video_db_id, result)
                connection.commit()
            return TranscriptionWorkerResult(
                handled=True,
                completed=True,
                failed=False,
                video_db_id=video_db_id,
            )
        except Exception as exc:
            error_message = str(exc)
            with mysql_connection(self.settings) as connection:
                TranscriptRepository(connection).mark_failed(video_db_id, error_message)
                connection.commit()
            return TranscriptionWorkerResult(
                handled=True,
                completed=False,
                failed=True,
                video_db_id=video_db_id,
                error_message=error_message,
            )
