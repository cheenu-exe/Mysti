"""Interactive chat REPL (Phase 0: Passive Mode only).

Chat with the configured LLM, plus /commands for direct memory management.
Works without an LLM configured: only the chat path needs one.
"""

import logging

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from mysti.core.context import AppContext
from mysti.exceptions import LLMError, RecordNotFoundError, ValidationError

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are MYSTI, the user's private AI assistant. "
    "You can remember and recall information the user stores, and you remember "
    "context from earlier in this conversation. "
    "You cannot access the user's system (Passive Mode). "
    "Be helpful, direct, and slightly technical. Ask for clarification when needed."
)

BANNER = """[bold cyan]MYSTI[/bold cyan] - your private AI memory (Phase 0)
Commands: /store /recall /categories /history /clear /status /help /quit"""

HELP_TEXT = """
[bold]/store <category> <text>[/bold] - store a memory
[bold]/recall <query>[/bold]          - search stored memories
[bold]/categories[/bold]              - list categories and counts
[bold]/history[/bold]                 - list recent conversations
[bold]/clear[/bold]                   - clear the visible conversation context
[bold]/status[/bold]                  - show system status
[bold]/help[/bold]                    - show this help
[bold]/quit[/bold]                    - exit
"""


class ChatRepl:
    """Read-eval-print loop for the MYSTI CLI."""

    def __init__(self, ctx: AppContext, console: Console | None = None) -> None:
        self._ctx = ctx
        self._console = console or Console()

    async def run(self) -> None:
        """Run the interactive loop until the user quits."""
        self._console.print(Panel(BANNER, border_style="cyan"))
        if self._ctx.first_run:
            self._console.print(
                "[yellow]First run: created your master key and key hierarchy.[/yellow]"
            )
        if self._ctx.settings.llm_provider == "none":
            self._console.print(
                "[yellow]No LLM configured (MYSTI_LLM_PROVIDER=none). "
                "Memory commands work; chat is disabled.[/yellow]"
            )
        session_id = await self._ctx.conversations.start_session()
        self._console.print(f"[dim]session {session_id[:8]}...[/dim]")
        while True:
            try:
                line = self._console.input("[bold cyan]you > [/bold cyan]").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not line:
                continue
            if line.startswith("/"):
                if not await self.handle_command(line, session_id):
                    break
            else:
                await self.chat(line, session_id)
        self._console.print("[dim]goodbye[/dim]")

    async def handle_command(self, line: str, session_id: str) -> bool:
        """Dispatch a /command. Returns False to exit the REPL."""
        parts = line.split(maxsplit=2)
        command = parts[0].lower()
        try:
            if command in ("/quit", "/exit"):
                return False
            if command == "/help":
                self._console.print(HELP_TEXT)
            elif command == "/clear":
                self._console.print("[dim]context cleared[/dim]")
            elif command == "/categories":
                await self._show_categories()
            elif command == "/history":
                await self._show_history()
            elif command == "/status":
                await self._show_status()
            elif command == "/store":
                if len(parts) < 3:
                    self._console.print("[red]usage: /store <category> <text>[/red]")
                else:
                    record = await self._ctx.memory.store(parts[1], parts[2])
                    self._console.print(f"[green]stored[/green] {record.id}")
            elif command == "/recall":
                if len(parts) < 2:
                    self._console.print("[red]usage: /recall <query>[/red]")
                else:
                    await self._show_recall(parts[1])
            else:
                self._console.print(f"[red]unknown command: {command}[/red] (try /help)")
        except (ValidationError, RecordNotFoundError, LLMError) as exc:
            self._console.print(f"[red]error:[/red] {exc}")
        return True

    async def chat(self, content: str, session_id: str) -> None:
        """Send a chat message to the LLM with conversation context."""
        try:
            await self._ctx.conversations.add_message(session_id, "user", content)
        except (ValidationError, RecordNotFoundError) as exc:
            self._console.print(f"[red]error:[/red] {exc}")
            return
        try:
            history = await self._ctx.conversations.build_context(session_id)
            reply = await self._ctx.llm.complete(
                [{"role": "system", "content": SYSTEM_PROMPT}, *history]
            )
        except LLMError as exc:
            self._console.print(f"[red]LLM error:[/red] {exc}")
            return
        await self._ctx.conversations.add_message(session_id, "assistant", reply)
        self._console.print(Markdown(reply))

    async def _show_categories(self) -> None:
        counts = await self._ctx.memory.list_categories()
        table = Table(title="Memory categories")
        table.add_column("category")
        table.add_column("records", justify="right")
        for name, count in sorted(counts.items()):
            table.add_row(name, str(count))
        self._console.print(table)

    async def _show_history(self) -> None:
        table = Table(title="Recent conversations")
        table.add_column("session")
        table.add_column("messages", justify="right")
        table.add_column("last activity")
        for session in await self._ctx.conversations.list_sessions():
            table.add_row(
                session.session_id[:8] + "...", str(session.message_count), session.last_at
            )
        self._console.print(table)

    async def _show_status(self) -> None:
        cache = self._ctx.cache.stats()
        self._console.print(
            f"records: [bold]{await self._ctx.memory.count_records()}[/bold]  "
            f"sessions: [bold]{await self._ctx.conversations.count_sessions()}[/bold]  "
            f"storage: [bold]{self._ctx.settings.storage_provider}[/bold]  "
            f"cache: [bold]{cache['entries']} entries "
            f"({cache['bytes'] / 1024:.1f} KiB in RAM)[/bold]"
        )

    async def _show_recall(self, query: str) -> None:
        hits = await self._ctx.memory.search(query)
        if not hits:
            self._console.print("[yellow]no matching memories[/yellow]")
            return
        table = Table(title=f"Recall: {query!r}")
        table.add_column("id")
        table.add_column("category")
        table.add_column("preview")
        for hit in hits:
            table.add_row(hit.id[:8] + "...", hit.category, hit.preview)
        self._console.print(table)
