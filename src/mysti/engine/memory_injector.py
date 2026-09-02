"""Memory injector: inserts ranked memories into LLM context.

Phase B adds:
- Token-aware injection (respects budget)
- Strategic placement (memories before user query)
- Formatting for LLM consumption
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class RankedMemory(Protocol):
    """Minimal ranked memory interface."""

    @property
    def hit(self) -> Any: ...
    @property
    def relevance_score(self) -> float: ...
    @property
    def reason(self) -> str: ...


@dataclass
class InjectionResult:
    """Result of injecting memories into a message list."""

    messages: list[dict[str, str]]
    memories_injected: int
    tokens_used: int
    budget_remaining: int


class MemoryInjector:
    """Injects ranked memories into the LLM message list.

    Memories are placed as a system message before the conversation,
    within the token budget.
    """

    def __init__(self, token_budget: int = 1024) -> None:
        self.token_budget = token_budget

    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimate: ~4 chars per token."""
        return max(1, len(text) // 4)

    def _format_memories(self, memories: list[RankedMemory]) -> str:
        """Format memories into a context block."""
        if not memories:
            return ""

        lines = ["## Relevant Memories"]
        for mem in memories:
            score_pct = int(mem.relevance_score * 100)
            preview = getattr(mem.hit, "preview", str(mem.hit))
            lines.append(f"- [{score_pct}%] {preview}")
        return "\n".join(lines)

    def inject(
        self,
        messages: list[dict[str, str]],
        memories: list[RankedMemory],
    ) -> InjectionResult:
        """Inject memories into the message list.

        Memories are formatted as a system message and placed before
        the conversation, respecting the token budget.

        Args:
            messages: Current message list (will not be mutated).
            memories: Ranked memories to inject.

        Returns:
            InjectionResult with updated messages and stats.
        """
        if not memories:
            return InjectionResult(
                messages=list(messages),
                memories_injected=0,
                tokens_used=0,
                budget_remaining=self.token_budget,
            )

        # Format memories
        memory_text = self._format_memories(memories)
        memory_tokens = self._estimate_tokens(memory_text)

        # Trim memories to fit budget
        selected_memories = memories
        while memory_tokens > self.token_budget and selected_memories:
            selected_memories = selected_memories[:-1]
            memory_text = self._format_memories(selected_memories)
            memory_tokens = self._estimate_tokens(memory_text)

        if not selected_memories:
            return InjectionResult(
                messages=list(messages),
                memories_injected=0,
                tokens_used=0,
                budget_remaining=self.token_budget,
            )

        # Build new message list: system message with memories, then existing messages
        result_messages: list[dict[str, str]] = []

        # Check if there's already a system message
        if messages and messages[0].get("role") == "system":
            # Append memories to existing system message
            existing_system = messages[0]["content"]
            combined = existing_system + "\n\n" + memory_text
            result_messages.append({"role": "system", "content": combined})
            result_messages.extend(messages[1:])
        else:
            # Insert new system message with memories
            result_messages.append({"role": "system", "content": memory_text})
            result_messages.extend(messages)

        return InjectionResult(
            messages=result_messages,
            memories_injected=len(selected_memories),
            tokens_used=memory_tokens,
            budget_remaining=max(0, self.token_budget - memory_tokens),
        )

    def inject_as_context(
        self,
        query: str,
        memories: list[RankedMemory],
    ) -> str:
        """Build a context string from memories for manual injection.

        Useful when you want to add memory context to a prompt
        without modifying the message list.
        """
        if not memories:
            return ""

        memory_text = self._format_memories(memories)
        memory_tokens = self._estimate_tokens(memory_text)

        # Trim to budget
        while memory_tokens > self.token_budget and memories:
            memories = memories[:-1]
            memory_text = self._format_memories(memories)
            memory_tokens = self._estimate_tokens(memory_text)

        return memory_text
