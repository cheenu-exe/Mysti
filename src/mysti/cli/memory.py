"""Memory CLI commands: `mysti memory ...` plus top-level `categories`/`consolidate`.

All commands accept ``--json`` for machine-readable output. Content is shown
as Markdown; category names are color-coded; consolidation shows a progress
bar. `mysti memory search` without a query enters interactive search mode.
"""

import asyncio
import json

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

from mysti.core.context import AppContext
from mysti.exceptions import MystiError
from mysti.memory.categories import CategoryManager
from mysti.memory.consolidation import MemoryConsolidator

memory_app = typer.Typer(
    name="memory", help="Store, search and manage memories.", no_args_is_help=True
)

console = Console()

CATEGORY_COLORS = {
    "personal": "cyan",
    "projects": "green",
    "relationships": "magenta",
    "technical": "blue",
    "research": "yellow",
    "ideas": "red",
}


def _run(coro) -> None:
    try:
        asyncio.run(coro)
    except MystiError as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc


async def _open_context() -> AppContext:
    from mysti.core.context import build_context

    return await build_context()


def _category_markup(category: str) -> str:
    color = CATEGORY_COLORS.get(category, "white")
    return f"[{color}]{category}[/{color}]"


def _echo_json(payload) -> None:
    console.print_json(json.dumps(payload, default=str))


def _hits_table(title: str, hits) -> None:
    table = Table(title=title)
    table.add_column("score", justify="right")
    table.add_column("id")
    table.add_column("category")
    table.add_column("preview")
    for hit in hits:
        table.add_row(
            f"{hit.score:.3f}", hit.id[:8] + "...", _category_markup(hit.category), hit.preview
        )
    console.print(table)


async def _interactive_search(ctx: AppContext, category: str | None, limit: int) -> None:
    console.print("[bold]Interactive memory search[/bold] (empty line to exit)")
    while True:
        try:
            query = console.input("[green]search>[/green] ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not query:
            break
        hits = await ctx.memory.search(query, category, limit)
        if not hits:
            console.print("[yellow]no matching memories[/yellow]")
        else:
            _hits_table(f"{len(hits)} result(s)", hits)


@memory_app.command("store")
def store(
    category: str,
    content: str,
    tags: str = typer.Option("", "--tags", help="Comma-separated tags."),
    importance: int = typer.Option(5, "--importance", min=1, max=10),
    source: str = typer.Option("chat", "--source"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Store a memory: mysti memory store <category> <content>."""
    tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]

    async def _impl():
        ctx = await _open_context()
        try:
            record = await ctx.memory.store(
                category, content, tags=tag_list, importance=importance, source=source
            )
            if as_json:
                _echo_json(record.model_dump())
            else:
                console.print(f"[green]stored[/green] {record.id} in {_category_markup(category)}")
        finally:
            await ctx.close()

    _run(_impl())


@memory_app.command("categories")
def categories(as_json: bool = typer.Option(False, "--json")) -> None:
    """List categories with record counts."""

    async def _impl():
        ctx = await _open_context()
        try:
            manager = CategoryManager(ctx.memory, ctx.keys, ctx.storage, ctx.audit)
            listed = await manager.list_categories()
            if as_json:
                _echo_json(listed)
                return
            table = Table(title="Memory categories")
            table.add_column("name")
            table.add_column("records", justify="right")
            table.add_column("priority", justify="right")
            table.add_column("description")
            for item in listed:
                table.add_row(
                    _category_markup(item["name"]),
                    str(item["count"]),
                    str(item["priority"]),
                    item["description"],
                )
            console.print(table)
        finally:
            await ctx.close()

    _run(_impl())


@memory_app.command("stats")
def stats(as_json: bool = typer.Option(False, "--json")) -> None:
    """Per-category memory statistics."""

    async def _impl():
        ctx = await _open_context()
        try:
            manager = CategoryManager(ctx.memory, ctx.keys, ctx.storage, ctx.audit)
            data = await manager.get_stats()
            if as_json:
                _echo_json(data)
                return
            table = Table(title=f"Memory stats ({data['total_records']} records)")
            table.add_column("category")
            table.add_column("records", justify="right")
            table.add_column("size", justify="right")
            table.add_column("avg importance", justify="right")
            for name, bucket in data["categories"].items():
                table.add_row(
                    _category_markup(name),
                    str(bucket["count"]),
                    f"{bucket['bytes'] / 1024:.1f} KiB",
                    str(bucket["avg_importance"]),
                )
            console.print(table)
        finally:
            await ctx.close()

    _run(_impl())


@memory_app.command("consolidate")
def consolidate(
    category: str | None = typer.Option(None, "--category", "-c"),
    skip_importance: bool = typer.Option(False, "--skip-importance"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Merge similar memories, remove duplicates and re-score importance."""

    async def _impl():
        ctx = await _open_context()
        try:
            consolidator = MemoryConsolidator(
                ctx.memory, ctx.audit, keys=ctx.keys, storage=ctx.storage
            )
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                console=console,
            ) as progress:
                task = progress.add_task("Consolidating...", total=1)
                job = await consolidator.run(category, skip_importance=skip_importance)
                progress.advance(task)
            if as_json:
                _echo_json(job)
            else:
                console.print(
                    f"[green]done[/green] · job {job['id'][:8]}... "
                    f"merged {job['merged']}, removed {job['removed']}, "
                    f"importance updated for {job['importance_updated']}"
                )
        finally:
            await ctx.close()

    _run(_impl())


@memory_app.command("consolidate-history")
def consolidate_history(
    limit: int = typer.Option(20, "--limit", "-l", min=1, max=50),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """List recent consolidation jobs."""

    async def _impl():
        ctx = await _open_context()
        try:
            consolidator = MemoryConsolidator(
                ctx.memory, ctx.audit, keys=ctx.keys, storage=ctx.storage
            )
            jobs = await consolidator.history(limit)
            if as_json:
                _echo_json(jobs)
                return
            table = Table(title="Consolidation jobs")
            table.add_column("id")
            table.add_column("category")
            table.add_column("status")
            table.add_column("merged", justify="right")
            table.add_column("removed", justify="right")
            table.add_column("started")
            for job in jobs:
                table.add_row(
                    job["id"][:8] + "...",
                    job.get("category") or "*",
                    job["status"],
                    str(job.get("merged", 0)),
                    str(job.get("removed", 0)),
                    (job.get("started_at") or "")[:19],
                )
            console.print(table)
        finally:
            await ctx.close()

    _run(_impl())


@memory_app.command("summaries")
def list_memories(
    category: str | None = typer.Option(None, "--category", "-c"),
    limit: int = typer.Option(20, "--limit", "-l", min=1),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """List memories (metadata only — content stays encrypted)."""

    async def _impl():
        ctx = await _open_context()
        try:
            entries = (await ctx.memory.entries(category))[:limit]
            if as_json:
                _echo_json([entry.model_dump() for entry in entries])
                return
            table = Table(title="Memories")
            table.add_column("id")
            table.add_column("category")
            table.add_column("imp", justify="right")
            table.add_column("acc", justify="right")
            table.add_column("tags")
            table.add_column("created")
            for entry in entries:
                table.add_row(
                    entry.id[:8] + "...",
                    _category_markup(entry.category),
                    str(entry.importance),
                    str(entry.access_count),
                    ", ".join(entry.tags),
                    entry.created_at[:19],
                )
            console.print(table)
        finally:
            await ctx.close()

    _run(_impl())


@memory_app.command("get")
def get(record_id: str, as_json: bool = typer.Option(False, "--json")) -> None:
    """Show one memory, decrypted, as Markdown."""

    async def _impl():
        ctx = await _open_context()
        try:
            record = await ctx.memory.retrieve(record_id)
            if as_json:
                _echo_json(record.model_dump())
                return
            console.print(f"[bold]{record.category}[/bold] · {record.created_at[:19]}")
            console.print(Markdown(record.content))
            console.print(
                f"tags: {', '.join(record.tags) or '—'} | importance: {record.importance} | "
                f"accesses: {record.access_count}"
            )
        finally:
            await ctx.close()

    _run(_impl())


@memory_app.command("suggest")
def suggest(
    query: str = typer.Argument(...),
    category: str | None = typer.Option(None, "--category", "-c"),
    limit: int = typer.Option(8, "--limit", "-l", min=1, max=50),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Suggest stored-memory terms completing QUERY (for autocomplete)."""

    async def _impl():
        ctx = await _open_context()
        try:
            terms = await ctx.memory.suggest(query, category, limit)
            if as_json:
                _echo_json(terms)
                return
            console.print("  ".join(terms) if terms else "[yellow]no suggestions[/yellow]")
        finally:
            await ctx.close()

    _run(_impl())


@memory_app.command("summarize")
def summarize(
    session_id: str,
    force: bool = typer.Option(False, "--force", help="Re-summarize the whole session."),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Summarize (or incrementally update) a conversation session."""

    async def _impl():
        ctx = await _open_context()
        try:
            if ctx.summarizer is None:
                raise MystiError("conversation summarizer is not available")
            summary = await ctx.summarizer.summarize(session_id, force=force)
            if as_json:
                _echo_json(summary.model_dump())
                return
            console.print(f"[bold]Summary[/bold] · v{summary.version} [{summary.model}]")
            console.print(Markdown(summary.summary or "_(no overview)_"))
            for label, items in (
                ("Topics", summary.key_topics),
                ("Facts", summary.key_facts),
                ("Decisions", summary.decisions),
                ("Actions", summary.action_items),
            ):
                if items:
                    console.print(f"\n[bold]{label}[/bold]")
                    for item in items:
                        console.print(f"  • {item}")
        finally:
            await ctx.close()

    _run(_impl())


@memory_app.command("delete")
def delete(record_id: str, as_json: bool = typer.Option(False, "--json")) -> None:
    """Soft-delete a memory."""

    async def _impl():
        ctx = await _open_context()
        try:
            await ctx.memory.delete(record_id)
            if as_json:
                _echo_json({"deleted": record_id})
            else:
                console.print(f"[red]deleted[/red] {record_id}")
        finally:
            await ctx.close()

    _run(_impl())


@memory_app.command("search")
def search(
    query: str | None = typer.Argument(None),
    category: str | None = typer.Option(None, "--category", "-c"),
    limit: int = typer.Option(10, "--limit", "-l", min=1),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Semantic + keyword search; omit QUERY for interactive mode."""

    async def _impl():
        ctx = await _open_context()
        try:
            if query is None:
                if as_json:
                    raise MystiError("--json is not supported in interactive search mode")
                await _interactive_search(ctx, category, limit)
                return
            hits = await ctx.memory.search(query, category, limit)
            if as_json:
                _echo_json([hit.model_dump() for hit in hits])
            elif not hits:
                console.print("[yellow]no matching memories[/yellow]")
            else:
                _hits_table(f"Search: {query!r}", hits)
        finally:
            await ctx.close()

    _run(_impl())
