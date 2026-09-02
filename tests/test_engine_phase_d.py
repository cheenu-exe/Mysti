"""Tests for AI Engine Phase D: Knowledge Integration.

Covers:
- EntityExtractor (extraction, parsing, storage)
- GraphQuery (search, context formatting)
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from mysti.engine.entity_extractor import (
    EntityExtractor,
    ExtractedEntity,
    ExtractedRelationship,
    ExtractionResult,
)
from mysti.engine.graph_query import GraphContext, GraphQuery


# ---- Helpers ----


class MockLLM:
    """Mock LLM that returns predefined extraction JSON."""

    def __init__(self, response: dict | None = None) -> None:
        self._response = response or {
            "entities": [
                {"name": "MYSTI", "entity_type": "project", "description": "AI operating layer", "confidence": 0.9}
            ],
            "relationships": []
        }
        self.call_count = 0

    async def complete(self, messages: list[dict[str, str]], **kwargs) -> str:
        self.call_count += 1
        return json.dumps(self._response)


class MockFailingLLM:
    """Mock LLM that always fails."""

    async def complete(self, messages: list[dict[str, str]], **kwargs) -> str:
        raise RuntimeError("LLM unavailable")


class MockMalformedLLM:
    """Mock LLM that returns non-JSON."""

    async def complete(self, messages: list[dict[str, str]], **kwargs) -> str:
        return "This is not JSON at all"


class MockGraph:
    """Mock knowledge graph for testing."""

    def __init__(self) -> None:
        self.entities: list = []
        self.relationships: list = []
        self.search_results: list = []
        self.add_entity_calls: list = []
        self.add_relationship_calls: list = []

    async def add_entity(self, entity) -> str:
        self.add_entity_calls.append(entity)
        self.entities.append(entity)
        return str(getattr(entity, "id", f"ent-{len(self.entities)}"))

    async def add_relationship(self, rel) -> str:
        self.add_relationship_calls.append(rel)
        self.relationships.append(rel)
        return str(getattr(rel, "id", f"rel-{len(self.relationships)}"))

    async def search(self, query: str) -> list:
        return self.search_results

    async def get_entity(self, entity_id: str):
        for e in self.entities:
            if str(getattr(e, "id", "")) == entity_id:
                return e
        return None

    async def get_relationships(self, entity_id: str) -> list:
        return [r for r in self.relationships
                if str(getattr(r, "source_id", "")) == entity_id
                or str(getattr(r, "target_id", "")) == entity_id]

    async def find_path(self, source: str, target: str) -> list[str]:
        return []


class MockEntity:
    """Mock entity for graph query tests."""

    def __init__(self, id: str, name: str, type: str = "concept", attributes: dict | None = None):
        self.id = id
        self.name = name
        self.type = type
        self.attributes = attributes or {}


class MockRelationship:
    """Mock relationship for graph query tests."""

    def __init__(self, id: str, source_id: str, target_id: str, type: str = "related_to"):
        self.id = id
        self.source_id = source_id
        self.target_id = target_id
        self.type = type


# ---- EntityExtractor tests ----


class TestEntityExtractor:
    @pytest.mark.asyncio
    async def test_extract_from_text(self):
        llm = MockLLM()
        extractor = EntityExtractor(llm=llm)
        result = await extractor.extract_from_text("I'm working on MYSTI")

        assert isinstance(result, ExtractionResult)
        assert len(result.entities) == 1
        assert result.entities[0].name == "MYSTI"
        assert result.entities[0].entity_type == "project"
        assert llm.call_count == 1

    @pytest.mark.asyncio
    async def test_extract_no_llm(self):
        extractor = EntityExtractor(llm=None)
        result = await extractor.extract_from_text("test")
        assert len(result.entities) == 0
        assert len(result.relationships) == 0

    @pytest.mark.asyncio
    async def test_extract_llm_failure(self):
        extractor = EntityExtractor(llm=MockFailingLLM())
        result = await extractor.extract_from_text("test")
        assert len(result.entities) == 0
        assert result.raw_response != ""

    @pytest.mark.asyncio
    async def test_extract_malformed_response(self):
        extractor = EntityExtractor(llm=MockMalformedLLM())
        result = await extractor.extract_from_text("test")
        assert len(result.entities) == 0

    @pytest.mark.asyncio
    async def test_extract_with_relationships(self):
        llm = MockLLM(response={
            "entities": [
                {"name": "MYSTI", "entity_type": "project", "description": "AI layer"},
                {"name": "Python", "entity_type": "technology", "description": "Programming language"},
            ],
            "relationships": [
                {"source_name": "MYSTI", "target_name": "Python", "relationship_type": "uses", "description": "Written in"}
            ]
        })
        extractor = EntityExtractor(llm=llm)
        result = await extractor.extract_from_text("MYSTI uses Python")

        assert len(result.entities) == 2
        assert len(result.relationships) == 1
        assert result.relationships[0].source_name == "MYSTI"
        assert result.relationships[0].relationship_type == "uses"

    @pytest.mark.asyncio
    async def test_extract_and_store(self):
        llm = MockLLM()
        graph = MockGraph()
        extractor = EntityExtractor(llm=llm, graph=graph)

        result = await extractor.extract_and_store("Working on MYSTI project")

        assert len(result.entities) == 1
        assert len(graph.add_entity_calls) == 1

    @pytest.mark.asyncio
    async def test_extract_and_store_no_graph(self):
        llm = MockLLM()
        extractor = EntityExtractor(llm=llm, graph=None)

        result = await extractor.extract_and_store("Working on MYSTI")
        assert len(result.entities) == 1

    @pytest.mark.asyncio
    async def test_extract_from_conversation(self):
        llm = MockLLM()
        extractor = EntityExtractor(llm=llm)

        messages = [
            {"role": "user", "content": "I'm building MYSTI"},
            {"role": "assistant", "content": "Great! What tech stack?"},
            {"role": "user", "content": "Using Python and FastAPI"},
        ]
        result = await extractor.extract_from_conversation(messages)
        assert result.source_text != ""

    def test_parse_response_valid(self):
        extractor = EntityExtractor()
        response = json.dumps({
            "entities": [{"name": "Test", "entity_type": "concept"}],
            "relationships": []
        })
        result = extractor._parse_response(response, "source")
        assert len(result.entities) == 1
        assert result.entities[0].name == "Test"

    def test_parse_response_with_json_in_text(self):
        extractor = EntityExtractor()
        response = 'Here is the extraction:\n{"entities": [{"name": "X", "entity_type": "concept"}], "relationships": []}\nDone.'
        result = extractor._parse_response(response, "source")
        assert len(result.entities) == 1

    def test_entity_id_generation(self):
        entity = ExtractedEntity(name="MYSTI Project", entity_type="project")
        assert entity.id == "ent-mysti-project"


# ---- GraphQuery tests ----


class TestGraphQuery:
    @pytest.mark.asyncio
    async def test_query_for_context(self):
        graph = MockGraph()
        graph.search_results = [
            MockEntity(id="e1", name="MYSTI", type="project", attributes={"description": "AI layer"}),
        ]
        query = GraphQuery(graph)
        context = await query.query_for_context("MYSTI project")

        assert isinstance(context, GraphContext)
        assert len(context.entities) == 1
        assert context.entity_count == 1

    @pytest.mark.asyncio
    async def test_query_no_results(self):
        graph = MockGraph()
        graph.search_results = []
        query = GraphQuery(graph)
        context = await query.query_for_context("nonexistent thing")

        assert len(context.entities) == 0
        assert context.relevance_score == 0.0

    @pytest.mark.asyncio
    async def test_query_includes_relationships(self):
        graph = MockGraph()
        graph.search_results = [MockEntity(id="e1", name="MYSTI", type="project")]
        graph.relationships = [MockRelationship(id="r1", source_id="e1", target_id="e2", type="uses")]
        query = GraphQuery(graph)
        context = await query.query_for_context("MYSTI")

        assert context.relationship_count == 1

    @pytest.mark.asyncio
    async def test_query_max_entities(self):
        graph = MockGraph()
        graph.search_results = [
            MockEntity(id=f"e{i}", name=f"Entity {i}", type="concept")
            for i in range(10)
        ]
        query = GraphQuery(graph)
        context = await query.query_for_context("test", max_entities=3)

        assert len(context.entities) == 3

    @pytest.mark.asyncio
    async def test_query_handles_search_error(self):
        class FailingGraph:
            async def search(self, query):
                raise RuntimeError("Graph down")
            async def get_relationships(self, eid):
                return []

        query = GraphQuery(FailingGraph())
        context = await query.query_for_context("test")
        assert len(context.entities) == 0

    def test_format_context_for_llm(self):
        context = GraphContext(
            query="test",
            entities=[MockEntity(id="e1", name="MYSTI", type="project", attributes={"description": "AI layer"})],
            relationships=[MockRelationship(id="r1", source_id="e1", target_id="e2", type="uses")],
            paths=[],
            relevance_score=0.8,
        )
        query = GraphQuery(MockGraph())
        text = query.format_context_for_llm(context)

        assert "Knowledge Graph Context" in text
        assert "MYSTI" in text
        assert "project" in text

    def test_format_context_empty(self):
        query = GraphQuery(MockGraph())
        context = GraphContext(query="test", entities=[], relationships=[], paths=[], relevance_score=0.0)
        text = query.format_context_for_llm(context)
        assert text == ""

    def test_get_entity_summary(self):
        context = GraphContext(
            query="test",
            entities=[
                MockEntity(id="e1", name="MYSTI", type="project"),
                MockEntity(id="e2", name="Python", type="technology"),
            ],
            relationships=[],
            paths=[],
            relevance_score=0.8,
        )
        query = GraphQuery(MockGraph())
        summary = query.get_entity_summary(context)
        assert "MYSTI" in summary
        assert "Python" in summary

    def test_get_entity_summary_empty(self):
        query = GraphQuery(MockGraph())
        context = GraphContext(query="test", entities=[], relationships=[], paths=[], relevance_score=0.0)
        summary = query.get_entity_summary(context)
        assert "No entities" in summary
