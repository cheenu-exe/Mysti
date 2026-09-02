"""Dynamic prompt builder: assembles system prompts from modular sections."""

from __future__ import annotations

from datetime import UTC, datetime


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


class DynamicPromptBuilder:
    """Builds a system prompt from a base prompt and optional sections.

    Usage::

        builder = DynamicPromptBuilder()
        builder.add_section("## Relevant Memories\\n- fact about user")
        builder.add_section("## Tool Definitions\\n- search: search the web")
        prompt = builder.build()
    """

    _DEFAULT_BASE = (
        "You are MYSTI, a private personal AI assistant. "
        "You help the user with research, memory, and tasks. "
        "You are concise, accurate, and respect the user's privacy. "
        "All data is encrypted and stored securely."
    )

    def __init__(self, base_system_prompt: str | None = None) -> None:
        self.base_prompt = base_system_prompt or self._DEFAULT_BASE
        self.sections: list[str] = []

    def add_section(self, content: str) -> None:
        """Add a content section to the prompt (skipped if empty)."""
        if content and content.strip():
            self.sections.append(content.strip())

    def add_memory_context(self, memories: list[str]) -> None:
        """Add a memories section from a list of memory previews."""
        if not memories:
            return
        lines = ["## Relevant Memories"]
        for mem in memories:
            lines.append(f"- {mem}")
        self.add_section("\\n".join(lines))

    def add_tool_definitions(self, tool_descriptions: list[str]) -> None:
        """Add tool definitions from formatted tool descriptions."""
        if not tool_descriptions:
            return
        lines = ["## Available Tools"]
        for desc in tool_descriptions:
            lines.append(f"- {desc}")
        self.add_section("\\n".join(lines))

    def add_knowledge_context(self, graph_context: str) -> None:
        """Add knowledge graph context."""
        if graph_context and graph_context.strip():
            self.add_section(graph_context)

    def build(self) -> str:
        """Assemble the final system prompt."""
        parts = [self.base_prompt]
        if self.sections:
            parts.append("\\n\\n".join(self.sections))
        return "\\n\\n".join(parts)
