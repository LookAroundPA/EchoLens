"""EchoLens command line interface."""

import typer

from echolens.collector.local_ingest import LocalIngestService
from echolens.collector.local_scanner import LocalSourceScanner
from echolens.core.config import get_settings

app = typer.Typer(help="EchoLens command line tools.")


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

    for item in items:
        typer.echo(
            f"- [{item.platform}] author={item.author_id} video={item.video_id} path={item.source_path}"
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
def worker() -> None:
    """Run the video processing worker."""

    typer.echo("Worker is not implemented yet.")


@app.command()
def analyze() -> None:
    """Run analysis for queued or pending content."""

    typer.echo("Analysis is not implemented yet.")
