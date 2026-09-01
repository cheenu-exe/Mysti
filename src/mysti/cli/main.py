"""MYSTI command-line interface.

Commands: init, start (chat REPL), store, recall, history, status, config, serve.
All configuration comes from MYSTI_* environment variables / .env; no secrets
are ever printed (the `config` command masks them).
"""

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from mysti import __version__
from mysti.cli.repl import ChatRepl
from mysti.core.context import AppContext, build_context
from mysti.exceptions import MystiError
from mysti.settings import Settings

app = typer.Typer(
    name="mysti", help="MYSTI - private, encrypted personal AI memory.", no_args_is_help=True
)
console = Console()

_SENSITIVE_FIELDS = ("key", "token", "secret", "passphrase")


def _run(coro) -> None:
    try:
        asyncio.run(coro)
    except MystiError as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc


async def _open_context() -> AppContext:
    return await build_context()


@app.command()
def init() -> None:
    """First-run setup: create the master key and category-key hierarchy."""
    _run(_init())


async def _init() -> None:
    ctx = await _open_context()
    try:
        if ctx.first_run:
            console.print("[green]Setup complete.[/green]")
            console.print("- Master key stored in your OS keystore (service 'mysti').")
            console.print("- Category keys created and uploaded wrapped to remote storage.")
            console.print(
                "[yellow]IMPORTANT:[/yellow] back up your master key offline. "
                "If it is lost, your encrypted memories are unrecoverable."
            )
        else:
            console.print("MYSTI is already initialized.")
    finally:
        await ctx.close()


@app.command()
def start() -> None:
    """Start the interactive chat session."""
    _run(_start())


async def _start() -> None:
    ctx = await _open_context()
    try:
        await ChatRepl(ctx, console).run()
    finally:
        await ctx.close()


@app.command()
def store(category: str, content: str) -> None:
    """Store a memory: mysti store <category> <content>."""
    _run(_store(category, content))


async def _store(category: str, content: str) -> None:
    ctx = await _open_context()
    try:
        record = await ctx.memory.store(category, content)
        console.print(f"[green]stored[/green] {record.id}")
    finally:
        await ctx.close()


@app.command()
def recall(query: str, category: str | None = None) -> None:
    """Search stored memories."""
    _run(_recall(query, category))


async def _recall(query: str, category: str | None) -> None:
    ctx = await _open_context()
    try:
        hits = await ctx.memory.search(query, category)
        if not hits:
            console.print("[yellow]no matching memories[/yellow]")
            return
        table = Table(title=f"Recall: {query!r}")
        table.add_column("id")
        table.add_column("category")
        table.add_column("preview")
        for hit in hits:
            table.add_row(hit.id[:8] + "...", hit.category, hit.preview)
        console.print(table)
    finally:
        await ctx.close()


@app.command()
def history(limit: int = 10) -> None:
    """Show recent conversation sessions."""
    _run(_history(limit))


async def _history(limit: int) -> None:
    ctx = await _open_context()
    try:
        table = Table(title="Recent conversations")
        table.add_column("session")
        table.add_column("messages", justify="right")
        table.add_column("last activity")
        for session in await ctx.conversations.list_sessions(limit):
            table.add_row(
                session.session_id[:8] + "...", str(session.message_count), session.last_at
            )
        console.print(table)
    finally:
        await ctx.close()


@app.command()
def status() -> None:
    """Show system status."""
    _run(_status())


async def _status() -> None:
    ctx = await _open_context()
    try:
        cache = ctx.cache.stats()
        console.print(f"version:     {__version__}")
        console.print(f"storage:     {ctx.settings.storage_provider}")
        console.print(f"records:     {await ctx.memory.count_records()}")
        console.print(f"sessions:    {await ctx.conversations.count_sessions()}")
        console.print(
            f"cache:       {cache['entries']} entries, {cache['bytes'] / 1024:.1f} KiB in RAM "
            f"(max {cache['max_bytes'] // (1024 * 1024)} MiB)"
        )
        console.print(f"llm:         {ctx.settings.llm_provider}")
        console.print(f"audit log:   {Path(ctx.settings.data_dir) / 'audit.jsonl'}")
    finally:
        await ctx.close()


@app.command()
def config() -> None:
    """Show configuration (secrets masked)."""
    settings = Settings()
    table = Table(title="MYSTI configuration")
    table.add_column("setting")
    table.add_column("value")
    for field_name, value in settings.model_dump().items():
        display = "***" if any(s in field_name for s in _SENSITIVE_FIELDS) and value else str(value)
        table.add_row(f"MYSTI_{field_name.upper()}", display)
    console.print(table)


@app.command()
def serve() -> None:
    """Run the Memory Service HTTP API."""
    _run(_serve())


async def _serve() -> None:
    import uvicorn

    ctx = await _open_context()
    from mysti.api.app import create_app

    application = create_app(ctx)
    server_config = uvicorn.Config(
        application,
        host=ctx.settings.api_host,
        port=ctx.settings.api_port,
        log_level=ctx.settings.log_level.lower(),
    )
    server = uvicorn.Server(server_config)
    try:
        await server.serve()
    finally:
        await ctx.close()


if __name__ == "__main__":
    app()
