"""CLI commands for research intelligence: `mysti briefing`, `mysti research`."""

import asyncio
import json

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

from mysti.research.briefing import DailyBriefing
from mysti.research.connectors import (
    ArxivConnector,
    GitHubConnector,
    HackerNewsConnector,
    RSSConnector,
    load_feeds,
)
from mysti.research.deep import DeepResearch
from mysti.research.relevance import RelevanceEngine

research_app = typer.Typer(name="research", help="Research intelligence commands.")
console = Console()


def _build_connectors() -> list:
    """Instantiate the default connector set (feeds from feeds.txt)."""
    connectors: list = [GitHubConnector(), ArxivConnector(), HackerNewsConnector()]
    feeds = load_feeds()
    if feeds:
        connectors.append(RSSConnector(feeds=feeds))
    return connectors


def _close(connectors: list) -> None:
    async def _aclose_all() -> None:
        for connector in connectors:
            await connector.aclose()

    asyncio.run(_aclose_all())


def briefing(date: str | None = None, as_json: bool = False) -> None:
    """Generate/show the daily briefing (default: today)."""
    connectors = _build_connectors()
    try:

        async def _run() -> dict:
            from mysti.core.context import build_context

            ctx = await build_context()
            try:
                engine = RelevanceEngine()
                service = DailyBriefing(connectors, engine, ctx.keys, ctx.storage, ctx.audit)
                return await service.get_briefing(date)
            finally:
                await ctx.close()

        data = asyncio.run(_run())
    finally:
        _close(connectors)
    _print_briefing(data, as_json)


def _print_briefing(data: dict, as_json: bool) -> None:
    if as_json:
        console.print_json(json.dumps(data))
        return
    console.rule(f"[bold]MYSTI Daily Briefing — {data['date']}")
    console.print(Markdown(data.get("summary", "")))
    stats = data.get("stats", {})
    console.print(
        f"[dim]{stats.get('items_scanned', 0)} scanned / "
        f"{stats.get('items_selected', 0)} selected / "
        f"{stats.get('sources_checked', 0)} sources[/dim]\n"
    )
    table = Table(title="Highlights")
    table.add_column("relevance", justify="right")
    table.add_column("source")
    table.add_column("title", overflow="fold")
    table.add_column("topic")
    for highlight in data.get("highlights", []):
        table.add_row(
            f"{highlight['relevance']:.1f}",
            highlight["source"],
            highlight["title"],
            highlight.get("bucket", "general"),
        )
    console.print(table)


def deep_research(topic: str, depth: int = 3, as_json: bool = False) -> None:
    """Run a deep research session: mysti research <topic> --depth 1-5."""
    connectors = _build_connectors()
    try:

        async def _run() -> dict:
            from mysti.core.context import build_context

            ctx = await build_context()
            try:
                engine = RelevanceEngine()
                service = DeepResearch(connectors, engine, ctx.keys, ctx.storage, ctx.audit)
                with console.status(f"[bold]Researching {topic!r} (depth {depth})..."):
                    session = await service.research(topic, depth=depth)
                return json.loads(session.model_dump_json())
            finally:
                await ctx.close()

        data = asyncio.run(_run())
    finally:
        _close(connectors)
    if as_json:
        console.print_json(json.dumps({k: v for k, v in data.items() if k != "findings"}))
        return
    console.print(Markdown(data.get("report", "")))


@research_app.command("run")
def research_cmd(
    topic: str,
    depth: int = typer.Option(3, "--depth", "-d", min=1, max=5),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Deep research on a topic across all sources."""
    deep_research(topic, depth=depth, as_json=as_json)


@research_app.command("sessions")
def sessions(as_json: bool = typer.Option(False, "--json")) -> None:
    """List past research sessions."""
    connectors = _build_connectors()
    try:

        async def _run() -> list[dict]:
            from mysti.core.context import build_context

            ctx = await build_context()
            try:
                engine = RelevanceEngine()
                service = DeepResearch(connectors, engine, ctx.keys, ctx.storage, ctx.audit)
                return await service.list_sessions()
            finally:
                await ctx.close()

        rows = asyncio.run(_run())
    finally:
        _close(connectors)
    if as_json:
        console.print_json(json.dumps(rows))
        return
    table = Table(title="Research sessions")
    table.add_column("id")
    table.add_column("topic")
    table.add_column("findings", justify="right")
    table.add_column("confidence", justify="right")
    for row in rows:
        table.add_row(
            row["id"][:8] + "...", row["topic"], str(row["findings"]), f"{row['confidence']:.2f}"
        )
    console.print(table)


def list_briefings(days: int = 7, as_json: bool = False) -> None:
    """List recent stored briefings."""
    connectors = _build_connectors()
    try:

        async def _run() -> list[dict]:
            from mysti.core.context import build_context

            ctx = await build_context()
            try:
                engine = RelevanceEngine()
                service = DailyBriefing(connectors, engine, ctx.keys, ctx.storage, ctx.audit)
                return await service.list_briefings(days)
            finally:
                await ctx.close()

        rows = asyncio.run(_run())
    finally:
        _close(connectors)
    if as_json:
        console.print_json(json.dumps(rows))
        return
    table = Table(title="Recent briefings")
    table.add_column("date")
    table.add_column("items", justify="right")
    table.add_column("summary", overflow="fold")
    for row in rows:
        table.add_row(row["date"], str(row["items_selected"]), row["summary"])
    console.print(table)
