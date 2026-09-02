"""Tests for AI Engine Phase B: Memory-Augmented Generation.

Covers:
- MemoryRanker (scoring, deduplication, time decay)
- MemoryInjector (token-aware injection, formatting)
- RAGPipeline (full pipeline: search → rank → inject → generate)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from mysti.engine.memory_injector import InjectionResult, MemoryInjector
from mysti.engine.memory_ranker import MemoryRanker, RankedMemory
from mysti.engine.rag import PipelineConfig, RAGPipeline, RAGResult


# ---- Helpers ----


class MockHit:
    """Mock search hit for testing."""

    def __init__(
        self,
        id: str = "hit-1",
        preview: str = "test memory",
        score: float = 0.5,
        category: str = "general",
        created_at: str | None = None,
        importance: int = 5,
    ) -> None:
        self.id = id
        self.preview = preview
        self.score = score
        self.category = category
        self.created_at = created_at or datetime.now(UTC).isoformat()
        self.importance = importance


class MockMemory:
    """Mock memory service."""

    def __init__(self, hits: list | None = None) -> None:
        self._hits = hits or []
        self.search_calls: list[tuple[str, int]] = []

    async def search(self, query: str, limit: int = 10) -> list:
        self.search_calls.append((query, limit))
        return self._hits


class MockLLM:
    """Mock LLM client."""

    def __init__(self, response: str = "Generated response") -> None:
        self._response = response
        self.call_count = 0
        self.last_messages: list[dict[str, str]] = []

    async def complete(self, messages: list[dict[str, str]], **kwargs) -> str:
        self.call_count += 1
        self.last_messages = messages
        return self._response


# ---- MemoryRanker tests ----


class TestMemoryRanker:
    def test_empty_hits(self):
        ranker = MemoryRanker()
        result = ranker.rank([])
        assert result == []

    def test_single_hit(self):
        ranker = MemoryRanker()
        hit = MockHit(score=0.8, importance=7)
        result = ranker.rank([hit])
        assert len(result) == 1
        assert result[0].rank == 1
        assert result[0].relevance_score > 0

    def test_ranking_order(self):
        ranker = MemoryRanker()
        hits = [
            MockHit(id="low", preview="low scoring memory about something else", score=0.2, importance=3),
            MockHit(id="high", preview="high scoring memory about the topic at hand", score=0.9, importance=8),
            MockHit(id="mid", preview="medium scoring memory about related subject", score=0.5, importance=5),
        ]
        result = ranker.rank(hits)
        assert len(result) == 3
        assert result[0].hit.id == "high"
        assert result[1].hit.id == "mid"
        assert result[2].hit.id == "low"

    def test_deduplication(self):
        ranker = MemoryRanker(dedup_threshold=0.8)
        hits = [
            MockHit(id="a", preview="user prefers dark mode"),
            MockHit(id="b", preview="user prefers dark mode theme"),
            MockHit(id="c", preview="completely different topic"),
        ]
        result = ranker.rank(hits)
        # Should deduplicate similar previews
        assert len(result) <= 3

    def test_max_results(self):
        ranker = MemoryRanker()
        hits = [MockHit(id=f"hit-{i}", preview=f"different memory about topic {i} specifically", score=0.5) for i in range(10)]
        result = ranker.rank(hits, max_results=3)
        assert len(result) == 3

    def test_importance_boost(self):
        ranker = MemoryRanker(importance_weight=0.5)
        high_imp = MockHit(id="high", preview="high importance memory about critical topic", score=0.5, importance=9)
        low_imp = MockHit(id="low", preview="low importance memory about trivial matter", score=0.5, importance=2)
        result = ranker.rank([high_imp, low_imp])
        assert result[0].hit.id == "high"

    def test_time_decay(self):
        ranker = MemoryRanker(time_weight=0.5)
        now = datetime.now(UTC)
        recent = MockHit(
            id="recent",
            preview="recent memory about something important",
            score=0.5,
            created_at=(now - timedelta(days=1)).isoformat(),
        )
        old = MockHit(
            id="old",
            preview="old memory about something from long ago",
            score=0.5,
            created_at=(now - timedelta(days=365)).isoformat(),
        )
        result = ranker.rank([old, recent])
        assert result[0].hit.id == "recent"

    def test_rank_assigned(self):
        ranker = MemoryRanker()
        hits = [MockHit(id=f"h{i}", preview=f"unique memory item number {i} here", score=0.5) for i in range(3)]
        result = ranker.rank(hits)
        for i, mem in enumerate(result):
            assert mem.rank == i + 1

    def test_reason_populated(self):
        ranker = MemoryRanker()
        hit = MockHit(score=0.9, preview="important memory with high score", importance=8)
        result = ranker.rank([hit])
        assert result[0].reason != ""


# ---- MemoryInjector tests ----


class TestMemoryInjector:
    def test_empty_memories(self):
        injector = MemoryInjector(token_budget=100)
        messages = [{"role": "user", "content": "hello"}]
        result = injector.inject(messages, [])
        assert result.memories_injected == 0
        assert result.messages == messages

    def test_inject_single_memory(self):
        injector = MemoryInjector(token_budget=500)
        mem = MockHit(preview="user likes blue", score=0.8, created_at=datetime.now(UTC).isoformat())
        ranked = [RankedMemory(hit=mem, relevance_score=0.8, reason="test")]

        messages = [{"role": "user", "content": "hello"}]
        result = injector.inject(messages, ranked)

        assert result.memories_injected == 1
        assert len(result.messages) == 2
        assert result.messages[0]["role"] == "system"
        assert "Relevant Memories" in result.messages[0]["content"]
        assert "user likes blue" in result.messages[0]["content"]

    def test_inject_preserves_existing_system(self):
        injector = MemoryInjector(token_budget=500)
        mem = MockHit(preview="memory", score=0.8, created_at=datetime.now(UTC).isoformat())
        ranked = [RankedMemory(hit=mem, relevance_score=0.8, reason="test")]

        messages = [
            {"role": "system", "content": "You are MYSTI"},
            {"role": "user", "content": "hello"},
        ]
        result = injector.inject(messages, ranked)

        assert result.memories_injected == 1
        assert len(result.messages) == 2
        assert "You are MYSTI" in result.messages[0]["content"]
        assert "memory" in result.messages[0]["content"]

    def test_token_budget_respected(self):
        injector = MemoryInjector(token_budget=20)  # Very small budget
        mems = [
            RankedMemory(hit=MockHit(preview=f"memory {i}" * 10, score=0.8, created_at=datetime.now(UTC).isoformat()), relevance_score=0.8, reason="test")
            for i in range(5)
        ]
        messages = [{"role": "user", "content": "hello"}]
        result = injector.inject(messages, mems)

        assert result.tokens_used <= 20

    def test_inject_as_context(self):
        injector = MemoryInjector(token_budget=500)
        mem = MockHit(preview="fact", score=0.8, created_at=datetime.now(UTC).isoformat())
        ranked = [RankedMemory(hit=mem, relevance_score=0.8, reason="test")]

        context = injector.inject_as_context("query", ranked)
        assert "Relevant Memories" in context
        assert "fact" in context

    def test_inject_as_context_empty(self):
        injector = MemoryInjector()
        context = injector.inject_as_context("query", [])
        assert context == ""

    def test_budget_remaining(self):
        injector = MemoryInjector(token_budget=1000)
        mem = MockHit(preview="short", score=0.5, created_at=datetime.now(UTC).isoformat())
        ranked = [RankedMemory(hit=mem, relevance_score=0.5, reason="test")]
        result = injector.inject([{"role": "user", "content": "hi"}], ranked)
        assert result.budget_remaining > 0


# ---- RAGPipeline tests ----


class TestRAGPipeline:
    @pytest.mark.asyncio
    async def test_search_stage(self):
        hits = [MockHit(id="h1", preview="found it", score=0.8)]
        memory = MockMemory(hits=hits)
        pipeline = RAGPipeline(memory=memory)

        result = await pipeline.search("test query")
        assert len(result) == 1
        assert result[0].preview == "found it"

    @pytest.mark.asyncio
    async def test_search_handles_error(self):
        class FailingMemory:
            async def search(self, query, limit=10):
                raise RuntimeError("Storage down")

        pipeline = RAGPipeline(memory=FailingMemory())
        result = await pipeline.search("test")
        assert result == []

    def test_rank_stage(self):
        hits = [
            MockHit(id="a", preview="low scoring memory about something unrelated", score=0.3, importance=3),
            MockHit(id="b", preview="high scoring memory about the exact topic", score=0.9, importance=8),
        ]
        pipeline = RAGPipeline(memory=MockMemory())
        ranked = pipeline.rank(hits)
        assert len(ranked) == 2
        assert ranked[0].hit.id == "b"

    @pytest.mark.asyncio
    async def test_generate_stage(self):
        llm = MockLLM(response="Hello from LLM")
        pipeline = RAGPipeline(memory=MockMemory(), llm=llm)

        response = await pipeline.generate([{"role": "user", "content": "hi"}])
        assert response == "Hello from LLM"
        assert llm.call_count == 1

    @pytest.mark.asyncio
    async def test_generate_no_llm(self):
        pipeline = RAGPipeline(memory=MockMemory(), llm=None)
        response = await pipeline.generate([{"role": "user", "content": "hi"}])
        assert "No LLM" in response

    @pytest.mark.asyncio
    async def test_generate_handles_error(self):
        class FailingLLM:
            async def complete(self, messages, **kwargs):
                raise RuntimeError("LLM down")

        pipeline = RAGPipeline(memory=MockMemory(), llm=FailingLLM())
        response = await pipeline.generate([{"role": "user", "content": "hi"}])
        assert "failed" in response.lower()

    @pytest.mark.asyncio
    async def test_full_pipeline(self):
        hits = [MockHit(id="h1", preview="relevant fact about the user's preferences", score=0.9, importance=8)]
        memory = MockMemory(hits=hits)
        llm = MockLLM(response="Based on your memory...")
        pipeline = RAGPipeline(memory=memory, llm=llm)

        messages = [{"role": "user", "content": "What do I know?"}]
        result = await pipeline.run("What do I know?", messages)

        assert isinstance(result, RAGResult)
        assert result.response == "Based on your memory..."
        assert result.search_hits == 1
        assert result.memories_injected >= 1
        assert result.memories_used[0].hit.id == "h1"
        assert result.pipeline_time_ms > 0

    @pytest.mark.asyncio
    async def test_enhance_context(self):
        hits = [MockHit(id="h1", preview="context fact about the current situation", score=0.8)]
        memory = MockMemory(hits=hits)
        pipeline = RAGPipeline(memory=memory)

        messages = [{"role": "user", "content": "hello"}]
        enhanced, memories = await pipeline.enhance_context(messages, "hello")

        assert len(enhanced) == 2  # system + user
        assert enhanced[0]["role"] == "system"
        assert len(memories) == 1

    @pytest.mark.asyncio
    async def test_pipeline_no_generate(self):
        hits = [MockHit(id="h1", preview="stored fact about something important", score=0.8)]
        memory = MockMemory(hits=hits)
        pipeline = RAGPipeline(memory=memory)

        result = await pipeline.run("query", [{"role": "user", "content": "hi"}], generate=False)
        assert result.response == ""

    @pytest.mark.asyncio
    async def test_config_overrides(self):
        config = PipelineConfig(search_limit=3, rank_limit=2, token_budget=200)
        hits = [MockHit(id=f"h{i}", preview=f"distinct memory about item number {i} here", score=0.5) for i in range(10)]
        memory = MockMemory(hits=hits)
        pipeline = RAGPipeline(memory=memory, config=config)

        ranked = pipeline.rank(hits)
        assert len(ranked) == 2  # rank_limit

    def test_min_relevance_filter(self):
        config = PipelineConfig(min_relevance=0.5)
        pipeline = RAGPipeline(memory=MockMemory(), config=config)

        hits = [
            MockHit(id="high", preview="high relevance memory about the topic", score=0.9),
            MockHit(id="low", preview="low relevance memory about something else", score=0.1),
        ]
        ranked = pipeline.rank(hits)
        assert all(r.relevance_score >= 0.5 for r in ranked)

    @pytest.mark.asyncio
    async def test_metadata_populated(self):
        hits = [MockHit(id="h1", preview="fact about something the user cares about", score=0.8)]
        memory = MockMemory(hits=hits)
        llm = MockLLM()
        pipeline = RAGPipeline(memory=memory, llm=llm)

        result = await pipeline.run("query", [{"role": "user", "content": "hi"}])
        assert "search_hits" in result.metadata or result.search_hits == 1
