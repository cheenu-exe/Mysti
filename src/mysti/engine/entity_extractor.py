"""Entity extractor: extracts entities and relationships from text into the knowledge graph.

Phase D implements:
- LLM-powered entity extraction with structured output
- Entity deduplication and merging
- Relationship extraction
- Graph population from conversation text
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


# ---- Protocols ----


class LLMClient(Protocol):
    """Minimal LLM interface for extraction."""

    async def complete(self, messages: list[dict[str, str]], **kwargs: Any) -> str: ...


class KnowledgeGraph(Protocol):
    """Knowledge graph storage interface."""

    async def add_entity(self, entity: Any) -> str: ...
    async def add_relationship(self, rel: Any) -> str: ...
    async def search(self, query: str) -> list[Any]: ...


# ---- Data models ----


@dataclass
class ExtractedEntity:
    """An entity extracted from text."""

    name: str
    entity_type: str  # "person", "project", "concept", "technology", "organization"
    description: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.8

    @property
    def id(self) -> str:
        return f"ent-{self.name.lower().replace(' ', '-')}"


@dataclass
class ExtractedRelationship:
    """A relationship extracted from text."""

    source_name: str
    target_name: str
    relationship_type: str  # "works_on", "uses", "depends_on", "related_to"
    description: str = ""
    confidence: float = 0.8


@dataclass
class ExtractionResult:
    """Result of entity extraction."""

    entities: list[ExtractedEntity]
    relationships: list[ExtractedRelationship]
    raw_response: str = ""
    source_text: str = ""


# ---- Extraction prompt ----

_EXTRACTION_PROMPT = """\
Extract entities and relationships from the following text.

Text: {text}

Return a JSON object with:
- entities: list of {{name, entity_type, description, confidence}}
  - entity_type must be one of: person, project, concept, technology, organization
- relationships: list of {{source_name, target_name, relationship_type, description, confidence}}
  - relationship_type must be one of: works_on, uses, depends_on, related_to, created_by, part_of

Only extract clearly stated entities and relationships. Be precise.
Return ONLY the JSON object, no other text."""


class EntityExtractor:
    """Extracts entities and relationships from text using an LLM.

    Optionally stores extracted entities in a KnowledgeGraph.
    """

    def __init__(
        self,
        llm: LLMClient | None = None,
        graph: KnowledgeGraph | None = None,
    ) -> None:
        self.llm = llm
        self.graph = graph

    async def extract_from_text(self, text: str) -> ExtractionResult:
        """Extract entities and relationships from text using the LLM.

        Falls back to empty extraction if LLM is unavailable or fails.
        """
        if self.llm is None:
            return ExtractionResult(entities=[], relationships=[], source_text=text)

        try:
            prompt = _EXTRACTION_PROMPT.format(text=text[:2000])  # Truncate for token limits
            response = await self.llm.complete([{"role": "user", "content": prompt}])
            return self._parse_response(response, text)
        except Exception as exc:
            logger.warning("Entity extraction failed: %s", exc)
            return ExtractionResult(entities=[], relationships=[], raw_response=str(exc), source_text=text)

    def _parse_response(self, response: str, source_text: str) -> ExtractionResult:
        """Parse LLM response into structured extraction result."""
        try:
            data = json.loads(response)
        except (json.JSONDecodeError, ValueError):
            # Try to find JSON in the response
            try:
                start = response.index("{")
                end = response.rindex("}") + 1
                data = json.loads(response[start:end])
            except (ValueError, IndexError):
                logger.debug("Failed to parse extraction response")
                return ExtractionResult(entities=[], relationships=[], raw_response=response, source_text=source_text)

        entities = []
        for item in data.get("entities", []):
            entities.append(ExtractedEntity(
                name=item.get("name", ""),
                entity_type=item.get("entity_type", "concept"),
                description=item.get("description", ""),
                confidence=float(item.get("confidence", 0.8)),
            ))

        relationships = []
        for item in data.get("relationships", []):
            relationships.append(ExtractedRelationship(
                source_name=item.get("source_name", ""),
                target_name=item.get("target_name", ""),
                relationship_type=item.get("relationship_type", "related_to"),
                description=item.get("description", ""),
                confidence=float(item.get("confidence", 0.8)),
            ))

        return ExtractionResult(
            entities=entities,
            relationships=relationships,
            raw_response=response,
            source_text=source_text,
        )

    async def extract_and_store(self, text: str) -> ExtractionResult:
        """Extract entities and store them in the knowledge graph.

        Returns the extraction result regardless of storage success.
        """
        result = await self.extract_from_text(text)

        if self.graph is None:
            return result

        # Store entities
        entity_ids: dict[str, str] = {}
        for entity in result.entities:
            try:
                # Create graph entity object
                graph_entity = _make_graph_entity(entity)
                entity_id = await self.graph.add_entity(graph_entity)
                entity_ids[entity.name] = entity_id
            except Exception as exc:
                logger.debug("Failed to store entity %s: %s", entity.name, exc)

        # Store relationships
        for rel in result.relationships:
            if rel.source_name in entity_ids and rel.target_name in entity_ids:
                try:
                    graph_rel = _make_graph_relationship(
                        entity_ids[rel.source_name],
                        entity_ids[rel.target_name],
                        rel,
                    )
                    await self.graph.add_relationship(graph_rel)
                except Exception as exc:
                    logger.debug("Failed to store relationship: %s", exc)

        return result

    async def extract_from_conversation(
        self,
        messages: list[dict[str, str]],
    ) -> ExtractionResult:
        """Extract entities from a conversation.

        Combines recent messages for context.
        """
        recent = messages[-10:]  # Last 10 messages
        text = "\n".join(f"{m.get('role', 'user')}: {m.get('content', '')}" for m in recent)
        return await self.extract_and_store(text)


def _make_graph_entity(entity: ExtractedEntity) -> Any:
    """Create a KnowledgeGraph-compatible entity object."""
    # Import the actual dataclass from integration module
    from mysti.integration.knowledge_graph import Entity
    return Entity(
        name=entity.name,
        type=entity.entity_type,
        attributes={
            "description": entity.description,
            "confidence": entity.confidence,
            **entity.attributes,
        },
    )


def _make_graph_relationship(
    source_id: str,
    target_id: str,
    rel: ExtractedRelationship,
) -> Any:
    """Create a KnowledgeGraph-compatible relationship object."""
    from mysti.integration.knowledge_graph import Relationship
    return Relationship(
        source_id=UUID(source_id),
        target_id=UUID(target_id),
        type=rel.relationship_type,
        metadata={
            "description": rel.description,
            "confidence": rel.confidence,
        },
    )
