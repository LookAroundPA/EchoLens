"""FFmpeg-backed, idempotent local audio extraction."""

from pathlib import Path, PureWindowsPath
import subprocess

from echolens.core.config import Settings


class AudioExtractionError(RuntimeError):
    """Raised when a source video cannot be converted to WAV."""


def resolve_source_path(stored_path: str, settings: Settings) -> Path:
    """Resolve a database path in the local or Docker filesystem namespace."""

    direct_path = Path(stored_path)
    if direct_path.is_file():
        return direct_path

    windows_path = PureWindowsPath(stored_path)
    host_root = PureWindowsPath(str(settings.douyin_source_host_dir))
    try:
        relative_path = windows_path.relative_to(host_root)
    except ValueError as exc:
        raise AudioExtractionError(f"Video path is outside the configured source root: {stored_path}") from exc

    mapped_path = settings.douyin_source_dir.joinpath(*relative_path.parts)
    if not mapped_path.is_file():
        raise AudioExtractionError(f"Video file is not available in this runtime: {mapped_path}")
    return mapped_path


def output_path_for(video: dict[str, object], settings: Settings) -> Path:
    """Build a deterministic WAV output path without allowing path traversal."""

    def safe_part(value: object) -> str:
        return str(value).replace("/", "_").replace("\\", "_").replace("..", "_")

    creator_identity = video.get("creator_sec_uid") or video.get("author_id")
    if not creator_identity:
        raise AudioExtractionError("Video row does not contain a creator identity.")

    return (
        settings.audio_output_dir
        / safe_part(video["platform"])
        / safe_part(creator_identity)
        / f"{safe_part(video['video_id'])}.wav"
    )


def extract_wav(source_path: Path, output_path: Path) -> int:
    """Extract mono 16 kHz PCM WAV, reusing an existing non-empty output."""

    if output_path.is_file() and output_path.stat().st_size > 44:
        return output_path.stat().st_size

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(f"{output_path.stem}.tmp.wav")
    temporary_path.unlink(missing_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-nostdin",
        "-i",
        str(source_path),
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "16000",
        "-ac",
        "1",
        str(temporary_path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0 or not temporary_path.is_file() or temporary_path.stat().st_size <= 44:
        temporary_path.unlink(missing_ok=True)
        detail = completed.stderr.strip()[-1000:]
        raise AudioExtractionError(f"FFmpeg extraction failed for {source_path}: {detail}")

    temporary_path.replace(output_path)
    return output_path.stat().st_size
