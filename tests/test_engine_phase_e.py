"""Tests for AI Engine Phase E: Intelligence Layer.

Covers:
- ModelRouter (routing, cost tracking, model registry)
- ProactiveEngine (suggestions from memory, knowledge, actions)
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from mysti.engine.model_router import ModelConfig, ModelRouter, ModelRouting
from mysti.engine.proactive_engine import ProactiveEngine, ProactiveSuggestion


# ---- Helpers ----


class MockMemory:
    """Mock memory service."""

    def __init__(self, hits: list | None = None) -> None:
        self._hits = hits or []
        self.search_calls: list[tuple[str, int]] = []

    async def search(self, query: str, limit: int = 5) -> list:
        self.search_calls.append((query, limit))
        return self._hits


class MockKnowledgeGraph:
    """Mock knowledge graph."""

    def __init__(self, entities: list | None = None) -> None:
        self._entities = entities or []

    async def search(self, query: str) -> list:
        return self._entities


class MockHit:
    """Mock search hit."""

    def __init__(self, id: str = "h1", preview: str = "memory content", score: float = 0.8):
        self.id = id
        self.preview = preview
        self.score = score


class MockEntity:
    """Mock entity."""

    def __init__(self, name: str = "MYSTI", type: str = "project"):
        self.name = name
        self.type = type


# ---- ModelRouter tests ----


class TestModelRouter:
    def test_default_models(self):
        router = ModelRouter()
        models = router.list_models()
        assert len(models) >= 3

    def test_get_model(self):
        router = ModelRouter()
        model = router.get_model("gpt-4o-mini")
        assert model is not None
        assert model.name == "GPT-4o Mini"

    def test_get_model_unknown(self):
        router = ModelRouter()
        assert router.get_model("nonexistent") is None

    def test_route_simple_question(self):
        router = ModelRouter()
        routing = router.route(intent="question", complexity="simple", domain="general")
        assert isinstance(routing, ModelRouting)
        assert routing.model_id
        assert routing.reason

    def test_route_complex_code(self):
        router = ModelRouter()
        routing = router.route(intent="command", complexity="complex", domain="code")
        # Should prefer a code-capable model
        model = router.get_model(routing.model_id)
        assert model is not None
        assert "code" in model.capabilities

    def test_route_simple_prefers_fast(self):
        router = ModelRouter()
        routing = router.route(intent="question", complexity="simple", domain="general")
        model = router.get_model(routing.model_id)
        assert model is not None
        # Simple tasks should prefer fast models
        assert model.average_latency_ms < 600

    def test_route_cost_estimate(self):
        router = ModelRouter()
        routing = router.route()
        assert routing.estimated_cost >= 0

    def test_cost_tracking(self):
        router = ModelRouter()
        router.route()
        router.route()
        report = router.get_cost_report()
        assert len(report) >= 1

    def test_reset_costs(self):
        router = ModelRouter()
        router.route()
        router.reset_costs()
        assert len(router.get_cost_report()) == 0

    def test_route_returns_reason(self):
        router = ModelRouter()
        routing = router.route(complexity="complex")
        assert len(routing.reason) > 0

    def test_custom_models(self):
        custom = [ModelConfig(model_id="custom", name="Custom", capabilities=["code"])]
        router = ModelRouter(models=custom)
        routing = router.route(domain="code")
        assert routing.model_id == "custom"


# ---- ProactiveEngine tests ----


class TestProactiveEngine:
    @pytest.mark.asyncio
    async def test_get_suggestions_empty(self):
        engine = ProactiveEngine()
        suggestions = await engine.get_suggestions("hello", [])
        assert isinstance(suggestions, list)

    @pytest.mark.asyncio
    async def test_memory_suggestions(self):
        hits = [MockHit(id="m1", preview="user prefers dark mode", score=0.9)]
        memory = MockMemory(hits=hits)
        engine = ProactiveEngine(memory=memory)

        suggestions = await engine.get_suggestions("What do I prefer?", [])
        assert len(suggestions) >= 1
        assert any(s.suggestion_type == "memory" for s in suggestions)

    @pytest.mark.asyncio
    async def test_memory_suggestions_low_score_filtered(self):
        hits = [MockHit(id="m1", preview="unrelated", score=0.3)]
        memory = MockMemory(hits=hits)
        engine = ProactiveEngine(memory=memory)

        suggestions = await engine.get_suggestions("test", [], min_relevance=0.5)
        assert len(suggestions) == 0

    @pytest.mark.asyncio
    async def test_knowledge_suggestions(self):
        entities = [MockEntity(name="MYSTI", type="project")]
        graph = MockKnowledgeGraph(entities=entities)
        engine = ProactiveEngine(knowledge_graph=graph)

        suggestions = await engine.get_suggestions("Tell me about MYSTI", [])
        assert len(suggestions) >= 1
        assert any(s.suggestion_type == "knowledge" for s in suggestions)

    @pytest.mark.asyncio
    async def test_action_suggestion_help(self):
        engine = ProactiveEngine()
        suggestions = await engine.get_suggestions("help me with this", [])
        assert any(s.suggestion_type == "action" and s.metadata.get("action") == "show_help" for s in suggestions)

    @pytest.mark.asyncio
    async def test_action_suggestion_research(self):
        engine = ProactiveEngine()
        suggestions = await engine.get_suggestions("research AI papers", [])
        assert any(s.suggestion_type == "action" and "research" in s.content.lower() for s in suggestions)

    @pytest.mark.asyncio
    async def test_action_suggestion_memory(self):
        engine = ProactiveEngine()
        suggestions = await engine.get_suggestions("remember this for later", [])
        assert any(s.suggestion_type == "action" and s.metadata.get("action") == "manage_memory" for s in suggestions)

    @pytest.mark.asyncio
    async def test_action_suggestion_project(self):
        engine = ProactiveEngine()
        suggestions = await engine.get_suggestions("check my project status", [])
        assert any(s.suggestion_type == "action" and "project" in s.content.lower() for s in suggestions)

    @pytest.mark.asyncio
    async def test_suggestions_sorted_by_relevance(self):
        hits = [MockHit(score=0.9), MockHit(score=0.7)]
        memory = MockMemory(hits=hits)
        graph = MockKnowledgeGraph(entities=[MockEntity()])
        engine = ProactiveEngine(memory=memory, knowledge_graph=graph)

        suggestions = await engine.get_suggestions("test query", [])
        scores = [s.relevance_score for s in suggestions]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_suggestions_limit(self):
        hits = [MockHit(score=0.9) for _ in range(10)]
        memory = MockMemory(hits=hits)
        engine = ProactiveEngine(memory=memory)

        suggestions = await engine.get_suggestions("test", [], limit=3)
        assert len(suggestions) <= 3

    @pytest.mark.asyncio
    async def test_no_memory_no_graph(self):
        engine = ProactiveEngine(memory=None, knowledge_graph=None)
        suggestions = await engine.get_suggestions("help me", [])
        # Should still get action suggestions
        assert len(suggestions) >= 1

    @pytest.mark.asyncio
    async def test_suggestion_metadata(self):
        hits = [MockHit(id="m1", preview="fact", score=0.8)]
        memory = MockMemory(hits=hits)
        engine = ProactiveEngine(memory=memory)

        suggestions = await engine.get_suggestions("test", [])
        for s in suggestions:
            assert isinstance(s.metadata, dict)

    @pytest.mark.asyncio
    async def test_suggestion_action_url(self):
        engine = ProactiveEngine()
        suggestions = await engine.get_suggestions("help me", [])
        for s in suggestions:
            if s.suggestion_type == "action":
                assert s.action_url is not None
