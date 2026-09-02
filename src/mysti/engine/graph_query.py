"""Graph query: queries the knowledge graph for context relevant to a conversation.

Phase D implements:
- Entity search by query
- Relationship traversal
- Path finding between entities
- Context formatting for LLM injection
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

logger = logging.getLogger(__name__)


# ---- Protocols ----


class KnowledgeGraph(Protocol):
    """Knowledge graph query interface."""

    async def search(self, query: str) -> list[Any]: ...
    async def get_entity(self, entity_id: str) -> Any: ...
    async def get_relationships(self, entity_id: str) -> list[Any]: ...
    async def find_path(self, source: str, target: str) -> list[str]: ...


# ---- Data models ----


@dataclass
class GraphContext:
    """Relevant graph data for a query."""

    query: str
    entities: list[Any]
    relationships: list[Any]
    paths: list[list[str]]
    relevance_score: float
    entity_count: int = 0
    relationship_count: int = 0


@dataclass
class EntityInfo:
    """Simplified entity information for context."""

    id: str
    name: str
    entity_type: str
    description: str
    attributes: dict[str, Any] = field(default_factory=dict)


class GraphQuery:
    """Queries the knowledge graph for context relevant to conversations."""

    def __init__(self, knowledge_graph: KnowledgeGraph) -> None:
        self.graph = knowledge_graph

    async def query_for_context(
        self,
        query: str,
        max_entities: int = 5,
        max_relationships: int = 10,
        max_depth: int = 2,
    ) -> GraphContext:
        """Search the knowledge graph for entities relevant to a query.

        Returns a GraphContext with matched entities, their relationships,
        and paths between them.
        """
        # Search for relevant entities
        try:
            entities = await self.graph.search(query)
        except Exception as exc:
            logger.warning("Graph search failed: %s", exc)
            entities = []

        entities = entities[:max_entities]

        if not entities:
            return GraphContext(
                query=query,
                entities=[],
                relationships=[],
                paths=[],
                relevance_score=0.0,
            )

        # Get relationships for each entity
        all_relationships: list[Any] = []
        for entity in entities:
            try:
                entity_id = getattr(entity, "id", None) or str(entity.get("id", ""))
                if entity_id:
                    rels = await self.graph.get_relationships(entity_id)
                    all_relationships.extend(rels)
            except Exception as exc:
                logger.debug("Failed to get relationships for entity: %s", exc)

        # Deduplicate relationships
        seen_ids: set[str] = set()
        unique_relationships: list[Any] = []
        for rel in all_relationships:
            rel_id = str(getattr(rel, "id", id(rel)))
            if rel_id not in seen_ids:
                seen_ids.add(rel_id)
                unique_relationships.append(rel)

        unique_relationships = unique_relationships[:max_relationships]

        # Find paths between entities (limited for performance)
        paths: list[list[str]] = []
        if len(entities) >= 2:
            for i in range(min(len(entities), 3)):
                for j in range(i + 1, min(len(entities), 4)):
                    try:
                        source_id = str(getattr(entities[i], "id", ""))
                        target_id = str(getattr(entities[j], "id", ""))
                        if source_id and target_id:
                            path = await self.graph.find_path(source_id, target_id)
                            if path:
                                paths.append(path)
                    except Exception:
                        pass

        # Calculate relevance score
        relevance_score = min(1.0, len(entities) / max_entities)

        return GraphContext(
            query=query,
            entities=entities,
            relationships=unique_relationships,
            paths=paths,
            relevance_score=round(relevance_score, 4),
            entity_count=len(entities),
            relationship_count=len(unique_relationships),
        )

    def format_context_for_llm(self, context: GraphContext) -> str:
        """Format graph context as a string for LLM injection."""
        if not context.entities:
            return ""

        lines = ["## Knowledge Graph Context"]

        # Entities
        lines.append("### Entities")
        for entity in context.entities:
            name = getattr(entity, "name", str(entity))
            entity_type = getattr(entity, "type", "unknown")
            attrs = getattr(entity, "attributes", {})
            description = attrs.get("description", "") if isinstance(attrs, dict) else ""
            if description:
                lines.append(f"- **{name}** ({entity_type}): {description}")
            else:
                lines.append(f"- **{name}** ({entity_type})")

        # Relationships
        if context.relationships:
            lines.append("\n### Relationships")
            for rel in context.relationships[:5]:  # Limit to 5
                rel_type = getattr(rel, "type", "related_to")
                source_id = str(getattr(rel, "source_id", "?"))
                target_id = str(getattr(rel, "target_id", "?"))
                lines.append(f"- {rel_type}: {source_id} -> {target_id}")

        # Paths
        if context.paths:
            lines.append("\n### Connections")
            for path in context.paths[:3]:  # Limit to 3
                if len(path) >= 2:
                    lines.append(f"- Connected: {' -> '.join(path[:4])}")

        return "\n".join(lines)

    def get_entity_summary(self, context: GraphContext) -> str:
        """Get a brief summary of entities in the context."""
        if not context.entities:
            return "No entities found."

        summaries = []
        for entity in context.entities:
            name = getattr(entity, "name", str(entity))
            entity_type = getattr(entity, "type", "unknown")
            summaries.append(f"{name} ({entity_type})")

        return ", ".join(summaries)
