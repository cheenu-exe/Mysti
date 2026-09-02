"""Agent state: tracks conversation, tool calls, and metadata per session."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class ToolCall:
    """Record of a single tool invocation."""

    tool_name: str
    arguments: dict
    result: str
    success: bool
    timestamp: str = field(default_factory=_iso_now)


@dataclass
class AgentState:
    """Mutable state for one agent session.

    Tracks the conversation messages, tool calls made, memories referenced,
    and metadata accumulated during a single ``AgentCore.chat()`` invocation.
    """

    session_id: str
    messages: list[dict[str, str]] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    memories_used: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    _started_at: str = field(default_factory=_iso_now)

    # ---- message helpers ----

    def add_message(self, role: str, content: str) -> None:
        """Append a message to the conversation history."""
        self.messages.append({"role": role, "content": content})

    def add_tool_call(self, call: ToolCall) -> None:
        """Record a tool invocation."""
        self.tool_calls.append(call)

    def to_context_messages(self, max_tokens: int = 4096) -> list[dict[str, str]]:
        """Return messages formatted for the LLM, trimmed to a token budget.

        Tokens are approximated as ``len(content) // 4``.
        """
        budget = max_tokens * 4
        selected: list[dict[str, str]] = []
        used = 0
        for msg in reversed(self.messages):
            cost = len(msg["content"])
            if selected and used + cost > budget:
                break
            selected.append(msg)
            used += cost
        selected.reverse()
        return selected

    def get_user_messages(self) -> list[dict[str, str]]:
        """Return only user messages."""
        return [m for m in self.messages if m["role"] == "user"]

    def get_assistant_messages(self) -> list[dict[str, str]]:
        """Return only assistant messages."""
        return [m for m in self.messages if m["role"] == "assistant"]

    def last_user_message(self) -> str | None:
        """Return the most recent user message content, or None."""
        for msg in reversed(self.messages):
            if msg["role"] == "user":
                return msg["content"]
        return None
