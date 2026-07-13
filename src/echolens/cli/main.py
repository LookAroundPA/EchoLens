"""EchoLens command line interface."""

import typer

from echolens.analysis_worker import AnalysisWorker
from echolens.collector.local_ingest import LocalIngestService
from echolens.collector.local_scanner import LocalSourceScanner
from echolens.core.config import Settings, get_settings
from echolens.transcription_worker import TranscriptionWorker
from echolens.worker import AudioWorker

app = typer.Typer(help="EchoLens command line tools.")


def _validate_limit_options(once: bool, max_tasks: int | None) -> int | None:
    if once and max_tasks is not None:
        raise typer.BadParameter("Use either --once or --max-tasks, not both.")
    return 1 if once else max_tasks


def _require_deepseek(settings: Settings) -> None:
    if settings.llm_provider.lower() != "deepseek":
        raise typer.BadParameter("Only LLM_PROVIDER=deepseek is implemented.")
    if not settings.llm_api_key:
        raise typer.BadParameter("LLM_API_KEY is required for DeepSeek analysis.")


def _run_audio_stage(settings: Settings, limit: int | None) -> tuple[int, int, int]:
    processed = completed = skipped = 0
    service = AudioWorker(settings=settings)
    while limit is None or processed < limit:
        result = service.process_one(timeout=1)
        if not result.handled:
            break
        processed += 1
        completed += int(result.completed)
        skipped += int(result.skipped)
    return processed, completed, skipped


def _run_transcription_stage(settings: Settings, limit: int | None) -> tuple[int, int, int]:
    processed = completed = failed = 0
    service = TranscriptionWorker(settings=settings)
    while limit is None or processed < limit:
        result = service.process_one()
        if not result.handled:
            break
        processed += 1
        completed += int(result.completed)
        failed += int(result.failed)
        if result.failed:
            typer.echo(
                f"! transcription_failed video_db_id={result.video_db_id} "
                f"message={result.error_message}",
                err=True,
            )
    return processed, completed, failed


def _run_analysis_stage(settings: Settings, limit: int | None) -> tuple[int, int, int]:
    processed = completed = failed = 0
    service = AnalysisWorker(settings=settings)
    while limit is None or processed < limit:
        result = service.process_one()
        if not result.handled:
            break
        processed += 1
        completed += int(result.completed)
        failed += int(result.failed)
        if result.failed:
            typer.echo(
                f"! analysis_failed video_db_id={result.video_db_id} "
                f"message={result.error_message}",
                err=True,
            )
    return processed, completed, failed


@app.command()
def scan(
    enqueue: bool = typer.Option(
        default=False,
        help="Write new videos to MySQL and push processing jobs to Redis.",
    ),
) -> None:
    """Scan the local Douyin source directory."""

    settings = get_settings()
    scanner = LocalSourceScanner(settings)
    items = scanner.scan()

    typer.echo(f"Source directory: {settings.douyin_source_dir}")
    typer.echo(f"Discovered valid video items: {len(items)}")
    typer.echo(f"Skipped source items: {len(scanner.issues)}")

    for item in items:
        typer.echo(
            "- "
            f"[{item.platform}] creator_sec_uid={item.creator_sec_uid} "
            f"creator={item.creator_name or '-'} video={item.video_id} path={item.source_path}"
        )

    for issue in scanner.issues:
        typer.echo(
            f"! [{issue.code}] video={issue.video_path} metadata={issue.metadata_path} "
            f"message={issue.message}",
            err=True,
        )

    if not enqueue:
        typer.echo("Dry run only. Use --enqueue to write MySQL and push Redis tasks.")
        return

    result = LocalIngestService().ingest(items)
    typer.echo("Ingest result:")
    typer.echo(f"  discovered: {result.discovered}")
    typer.echo(f"  inserted: {result.inserted}")
    typer.echo(f"  queued: {result.queued}")
    typer.echo(f"  skipped_existing: {result.skipped_existing}")


@app.command()
def worker(
    once: bool = typer.Option(default=False, help="Process at most one task and exit."),
    max_tasks: int | None = typer.Option(default=None, min=1, help="Maximum tasks to process before exit."),
) -> None:
    """Extract WAV files for queued videos."""

    limit = _validate_limit_options(once, max_tasks)
    processed, completed, skipped = _run_audio_stage(get_settings(), limit)
    typer.echo(f"Worker result: processed={processed} completed={completed} skipped={skipped}")


@app.command()
def transcribe(
    once: bool = typer.Option(default=False, help="Transcribe at most one audio file and exit."),
    max_tasks: int | None = typer.Option(default=None, min=1, help="Maximum audio files to transcribe."),
) -> None:
    """Transcribe audio_done videos with Faster-Whisper."""

    limit = _validate_limit_options(once, max_tasks)
    settings = get_settings()
    typer.echo(
        "Transcription model: "
        f"{settings.whisper_model} device={settings.whisper_device} "
        f"compute_type={settings.whisper_compute_type}"
    )

    processed, completed, failed = _run_transcription_stage(settings, limit)
    typer.echo(
        f"Transcription result: processed={processed} completed={completed} failed={failed}"
    )


@app.command()
def analyze(
    once: bool = typer.Option(default=False, help="Analyze at most one transcript and exit."),
    max_tasks: int | None = typer.Option(default=None, min=1, help="Maximum transcripts to analyze."),
) -> None:
    """Analyze transcribed videos with DeepSeek."""

    limit = _validate_limit_options(once, max_tasks)
    settings = get_settings()
    _require_deepseek(settings)
    typer.echo(f"Analysis model: provider={settings.llm_provider} model={settings.llm_model}")

    processed, completed, failed = _run_analysis_stage(settings, limit)
    typer.echo(f"Analysis result: processed={processed} completed={completed} failed={failed}")


@app.command()
def pipeline(
    max_tasks: int | None = typer.Option(
        default=None,
        min=1,
        help="Maximum items processed in each stage; omit to drain all available work.",
    ),
) -> None:
    """Run audio extraction, transcription, and DeepSeek analysis in sequence."""

    settings = get_settings()
    _require_deepseek(settings)

    audio_processed, audio_completed, audio_skipped = _run_audio_stage(settings, max_tasks)
    transcription_processed, transcription_completed, transcription_failed = (
        _run_transcription_stage(settings, max_tasks)
    )
    analysis_processed, analysis_completed, analysis_failed = _run_analysis_stage(
        settings,
        max_tasks,
    )

    typer.echo("Pipeline result:")
    typer.echo(
        "  audio: "
        f"processed={audio_processed} completed={audio_completed} skipped={audio_skipped}"
    )
    typer.echo(
        "  transcription: "
        f"processed={transcription_processed} completed={transcription_completed} "
        f"failed={transcription_failed}"
    )
    typer.echo(
        "  analysis: "
        f"processed={analysis_processed} completed={analysis_completed} failed={analysis_failed}"
    )
