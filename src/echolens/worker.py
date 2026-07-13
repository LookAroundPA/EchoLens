"""Worker that extracts durable WAV files from queued videos."""

from dataclasses import dataclass

from echolens.audio.ffmpeg import extract_wav, output_path_for, resolve_source_path
from echolens.core.config import Settings, get_settings
from echolens.storage.mysql import mysql_connection
from echolens.storage.redis_queue import VideoQueue
from echolens.storage.video_repository import VideoRepository


@dataclass(frozen=True)
class WorkerResult:
    handled: bool
    completed: bool
    skipped: bool


class AudioWorker:
    """Advance queued videos to audio_done."""

    def __init__(self, settings: Settings | None = None, queue: VideoQueue | None = None) -> None:
        self.settings = settings or get_settings()
        self.queue = queue or VideoQueue(settings=self.settings)

    def process_one(self, timeout: int = 5) -> WorkerResult:
        """Reserve, process, and acknowledge at most one Redis task."""

        reserved = self.queue.reserve(timeout=timeout)
        if reserved is None:
            return WorkerResult(handled=False, completed=False, skipped=False)
        raw_payload, payload = reserved
        video_db_id = int(payload["video_db_id"])

        try:
            result = self.process_video(video_db_id)
            self.queue.acknowledge(raw_payload)
            return result
        except Exception:
            self.queue.retry(raw_payload)
            raise

    def process_video(self, video_db_id: int, *, force: bool = False) -> WorkerResult:
        """Extract audio for one specific video already in queued status."""

        try:
            with mysql_connection(self.settings) as connection:
                repository = VideoRepository(connection)
                video = repository.claim_video_for_audio(video_db_id)
                if video is None:
                    connection.commit()
                    return WorkerResult(handled=True, completed=False, skipped=True)

                source_path = resolve_source_path(str(video["file_path"]), self.settings)
                audio_path = output_path_for(video, self.settings)
                if force:
                    audio_path.unlink(missing_ok=True)
                audio_size = extract_wav(source_path, audio_path)
                repository.mark_audio_done(video_db_id, str(audio_path), audio_size)
                connection.commit()
            return WorkerResult(handled=True, completed=True, skipped=False)
        except Exception as exc:
            with mysql_connection(self.settings) as connection:
                VideoRepository(connection).release_video_for_retry(video_db_id, str(exc))
                connection.commit()
            raise
