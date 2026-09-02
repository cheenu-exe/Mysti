"""Proactive engine: surfaces relevant information before being asked.

Phase E implements:
- Context-aware suggestion generation
- Memory-based suggestions
- Knowledge graph-based suggestions
- Action suggestions based on conversation
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

logger = logging.getLogger(__name__)


# ---- Protocols ----


class MemoryService(Protocol):
    """Memory search interface."""

    async def search(self, query: str, limit: int = 5) -> list[Any]: ...


class KnowledgeGraph(Protocol):
    """Knowledge graph search interface."""

    async def search(self, query: str) -> list[Any]: ...


# ---- Data models ----


@dataclass
class ProactiveSuggestion:
    """A suggestion for proactive behavior."""

    suggestion_type: str  # "memory", "knowledge", "action", "related"
    content: str
    relevance_score: float
    action_url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ProactiveEngine:
    """Surfaces relevant information proactively based on context.

    Checks for:
    - Related memories that might be useful
    - Knowledge graph entities relevant to the conversation
    - Potential actions the user might want to take
    """

    def __init__(
        self,
        memory: MemoryService | None = None,
        knowledge_graph: KnowledgeGraph | None = None,
    ) -> None:
        self.memory = memory
        self.knowledge_graph = knowledge_graph

    async def get_suggestions(
        self,
        current_message: str,
        conversation_history: list[dict[str, str]],
        limit: int = 5,
        min_relevance: float = 0.5,
    ) -> list[ProactiveSuggestion]:
        """Get proactive suggestions based on current context.

        Args:
            current_message: The latest user message.
            conversation_history: Recent conversation messages.
            limit: Maximum suggestions to return.
            min_relevance: Minimum relevance score to include.

        Returns:
            List of suggestions sorted by relevance.
        """
        suggestions: list[ProactiveSuggestion] = []

        # Check memory
        memory_suggestions = await self._get_memory_suggestions(current_message)
        suggestions.extend(memory_suggestions)

        # Check knowledge graph
        knowledge_suggestions = await self._get_knowledge_suggestions(current_message)
        suggestions.extend(knowledge_suggestions)

        # Check for action suggestions
        action_suggestions = self._get_action_suggestions(current_message, conversation_history)
        suggestions.extend(action_suggestions)

        # Sort by relevance and filter
        suggestions.sort(key=lambda s: s.relevance_score, reverse=True)
        suggestions = [s for s in suggestions if s.relevance_score >= min_relevance]

        return suggestions[:limit]

    async def _get_memory_suggestions(
        self,
        current_message: str,
    ) -> list[ProactiveSuggestion]:
        """Find relevant memories that might be useful."""
        if self.memory is None:
            return []

        suggestions: list[ProactiveSuggestion] = []
        try:
            hits = await self.memory.search(current_message, limit=3)
            for hit in hits:
                score = getattr(hit, "score", 0.5) or 0.5
                if score > 0.6:
                    preview = getattr(hit, "preview", str(hit))
                    suggestions.append(ProactiveSuggestion(
                        suggestion_type="memory",
                        content=f"Relevant memory: {preview[:100]}",
                        relevance_score=score,
                        action_url=f"/memory/{getattr(hit, 'id', '')}",
                        metadata={"memory_id": getattr(hit, "id", "")},
                    ))
        except Exception as exc:
            logger.debug("Memory suggestion failed: %s", exc)

        return suggestions

    async def _get_knowledge_suggestions(
        self,
        current_message: str,
    ) -> list[ProactiveSuggestion]:
        """Find relevant knowledge graph entities."""
        if self.knowledge_graph is None:
            return []

        suggestions: list[ProactiveSuggestion] = []
        try:
            entities = await self.knowledge_graph.search(current_message)
            for entity in entities[:2]:
                name = getattr(entity, "name", str(entity))
                entity_type = getattr(entity, "type", "unknown")
                suggestions.append(ProactiveSuggestion(
                    suggestion_type="knowledge",
                    content=f"Related: {name} ({entity_type})",
                    relevance_score=0.7,
                    action_url=f"/knowledge/{name}",
                    metadata={"entity_name": name, "entity_type": entity_type},
                ))
        except Exception as exc:
            logger.debug("Knowledge suggestion failed: %s", exc)

        return suggestions

    def _get_action_suggestions(
        self,
        current_message: str,
        conversation_history: list[dict[str, str]],
    ) -> list[ProactiveSuggestion]:
        """Suggest actions based on conversation context."""
        suggestions: list[ProactiveSuggestion] = []
        lower = current_message.lower()

        if "remember" in lower or "forget" in lower:
            suggestions.append(ProactiveSuggestion(
                suggestion_type="action",
                content="Manage your memories",
                relevance_score=0.8,
                action_url="/memory",
                metadata={"action": "manage_memory"},
            ))

        if "research" in lower or "find" in lower or "search" in lower:
            suggestions.append(ProactiveSuggestion(
                suggestion_type="action",
                content="Start a research session",
                relevance_score=0.7,
                action_url="/research",
                metadata={"action": "start_research"},
            ))

        if "project" in lower:
            suggestions.append(ProactiveSuggestion(
                suggestion_type="action",
                content="View project dashboard",
                relevance_score=0.6,
                action_url="/dashboard",
                metadata={"action": "view_dashboard"},
            ))

        if "help" in lower:
            suggestions.append(ProactiveSuggestion(
                suggestion_type="action",
                content="View available commands",
                relevance_score=0.9,
                action_url="/help",
                metadata={"action": "show_help"},
            ))

        return suggestions
