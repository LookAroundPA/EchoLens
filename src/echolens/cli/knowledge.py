"""CLI commands for querying completed EchoLens knowledge."""

from __future__ import annotations

from enum import Enum

import typer

from echolens.knowledge.formatters import (
    render_creators_text,
    render_item_markdown,
    render_items_markdown,
    render_items_text,
    render_json,
)
from echolens.storage.knowledge_repository import KnowledgeRepository
from echolens.storage.mysql import mysql_connection


class OutputFormat(str, Enum):
    text = "text"
    markdown = "markdown"
    json = "json"


knowledge_app = typer.Typer(help="Query completed transcripts and analyses.")


@knowledge_app.command("creators")
def creators(
    limit: int = typer.Option(default=100, min=1, max=1000),
    output_format: OutputFormat = typer.Option(OutputFormat.text, "--format"),
) -> None:
    """List creators and their available completed knowledge."""

    with mysql_connection() as connection:
        rows = KnowledgeRepository(connection).list_creators(limit=limit)

    if output_format == OutputFormat.json:
        typer.echo(render_json(rows))
    else:
        typer.echo(render_creators_text(rows))


@knowledge_app.command("list")
def list_content(
    creator: str | None = typer.Option(default=None, help="Filter by creator sec_uid."),
    tag: str | None = typer.Option(default=None, help="Filter by an exact analysis tag."),
    limit: int = typer.Option(default=20, min=1, max=500),
    output_format: OutputFormat = typer.Option(OutputFormat.text, "--format"),
) -> None:
    """List completed knowledge items."""

    with mysql_connection() as connection:
        rows = KnowledgeRepository(connection).list_items(
            creator_sec_uid=creator,
            tag=tag,
            limit=limit,
        )

    if output_format == OutputFormat.json:
        typer.echo(render_json(rows))
    elif output_format == OutputFormat.markdown:
        typer.echo(render_items_markdown(rows))
    else:
        typer.echo(render_items_text(rows))


@knowledge_app.command("search")
def search(
    query: str = typer.Argument(..., help="Keyword matched against transcript and analysis text."),
    creator: str | None = typer.Option(default=None, help="Filter by creator sec_uid."),
    tag: str | None = typer.Option(default=None, help="Filter by an exact analysis tag."),
    limit: int = typer.Option(default=20, min=1, max=500),
    output_format: OutputFormat = typer.Option(OutputFormat.text, "--format"),
) -> None:
    """Search descriptions, transcripts, summaries, tags, and key points."""

    with mysql_connection() as connection:
        rows = KnowledgeRepository(connection).list_items(
            creator_sec_uid=creator,
            tag=tag,
            keyword=query,
            limit=limit,
        )

    if output_format == OutputFormat.json:
        typer.echo(render_json(rows))
    elif output_format == OutputFormat.markdown:
        typer.echo(render_items_markdown(rows))
    else:
        typer.echo(render_items_text(rows))


@knowledge_app.command("show")
def show(
    video_id: str = typer.Argument(..., help="Platform video id."),
    creator: str | None = typer.Option(
        default=None,
        help="Creator sec_uid, required only when a video id is ambiguous.",
    ),
    output_format: OutputFormat = typer.Option(OutputFormat.markdown, "--format"),
) -> None:
    """Show one completed video's metadata, analysis, and full transcript."""

    with mysql_connection() as connection:
        rows = KnowledgeRepository(connection).find_video(
            video_id=video_id,
            creator_sec_uid=creator,
        )

    if not rows:
        typer.echo(f"No completed knowledge found for video_id={video_id}", err=True)
        raise typer.Exit(code=1)
    if len(rows) > 1:
        typer.echo(
            "Multiple creators contain this video id; rerun with --creator <sec_uid>.",
            err=True,
        )
        raise typer.Exit(code=2)

    item = rows[0]
    if output_format == OutputFormat.json:
        typer.echo(render_json(item))
    elif output_format == OutputFormat.text:
        typer.echo(render_items_text([item]))
    else:
        typer.echo(render_item_markdown(item))
