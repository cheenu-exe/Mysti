"""RAG pipeline: Retrieve-and-Generate with memory augmentation.

Phase B implements:
- Search → Rank → Inject → Generate pipeline
- Configurable pipeline stages
- Token budget management
- Result tracking and metadata
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

from mysti.engine.memory_injector import InjectionResult, MemoryInjector
from mysti.engine.memory_ranker import MemoryRanker, RankedMemory

logger = logging.getLogger(__name__)


# ---- Protocols ----


class SearchHit(Protocol):
    """Minimal search hit from memory service."""

    @property
    def id(self) -> str: ...
    @property
    def preview(self) -> str: ...
    @property
    def score(self) -> float: ...
    @property
    def category(self) -> str: ...
    @property
    def created_at(self) -> str: ...


class MemoryService(Protocol):
    """Memory service with search capability."""

    async def search(self, query: str, limit: int = 10) -> list[SearchHit]: ...


class LLMClient(Protocol):
    """LLM client for generation."""

    async def complete(self, messages: list[dict[str, str]], **kwargs: Any) -> str: ...


# ---- Pipeline result ----


@dataclass
class RAGResult:
    """Result of the RAG pipeline."""

    response: str
    memories_used: list[RankedMemory]
    query: str
    search_hits: int
    memories_ranked: int
    memories_injected: int
    tokens_used: int
    pipeline_time_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


# ---- Pipeline stages ----


@dataclass
class PipelineConfig:
    """Configuration for the RAG pipeline."""

    search_limit: int = 10
    rank_limit: int = 5
    token_budget: int = 1024
    min_relevance: float = 0.1
    boost_importance: bool = True
    apply_time_decay: bool = True


class RAGPipeline:
    """Retrieve-Augmented Generation pipeline.

    Stages:
    1. Search: Find relevant memories from the memory service
    2. Rank: Score and rank by relevance, importance, recency
    3. Inject: Insert top-ranked memories into LLM context
    4. Generate: Call LLM with augmented context
    """

    def __init__(
        self,
        memory: MemoryService,
        llm: LLMClient | None = None,
        ranker: MemoryRanker | None = None,
        injector: MemoryInjector | None = None,
        config: PipelineConfig | None = None,
    ) -> None:
        self.memory = memory
        self.llm = llm
        self.ranker = ranker or MemoryRanker()
        self.injector = injector or MemoryInjector()
        self.config = config or PipelineConfig()

    async def search(self, query: str) -> list[SearchHit]:
        """Stage 1: Search for relevant memories."""
        try:
            hits = await self.memory.search(query, limit=self.config.search_limit)
            logger.debug("Search returned %d hits for query: %s", len(query), query[:50])
            return hits
        except Exception as exc:
            logger.warning("Memory search failed: %s", exc)
            return []

    def rank(self, hits: list[SearchHit]) -> list[RankedMemory]:
        """Stage 2: Rank search hits by relevance."""
        ranked = self.ranker.rank(
            hits,
            max_results=self.config.rank_limit,
            boost_importance=self.config.boost_importance,
            apply_time_decay=self.config.apply_time_decay,
        )
        # Filter by minimum relevance
        ranked = [r for r in ranked if r.relevance_score >= self.config.min_relevance]
        logger.debug("Ranked %d memories (from %d hits)", len(ranked), len(hits))
        return ranked

    def inject(
        self,
        messages: list[dict[str, str]],
        memories: list[RankedMemory],
    ) -> InjectionResult:
        """Stage 3: Inject memories into message context."""
        self.injector.token_budget = self.config.token_budget
        result = self.injector.inject(messages, memories)
        logger.debug(
            "Injected %d memories, tokens used: %d",
            result.memories_injected,
            result.tokens_used,
        )
        return result

    async def generate(
        self,
        messages: list[dict[str, str]],
    ) -> str:
        """Stage 4: Generate response from LLM."""
        if self.llm is None:
            return "[No LLM configured - memory context only]"
        try:
            return await self.llm.complete(messages)
        except Exception as exc:
            logger.error("LLM generation failed: %s", exc)
            return f"[Generation failed: {exc}]"

    async def run(
        self,
        query: str,
        messages: list[dict[str, str]],
        *,
        generate: bool = True,
    ) -> RAGResult:
        """Execute the full RAG pipeline.

        Args:
            query: User query for memory search.
            messages: Current conversation messages.
            generate: Whether to call the LLM for generation.

        Returns:
            RAGResult with response, memories, and stats.
        """
        import time
        start = time.monotonic()

        # Stage 1: Search
        hits = await self.search(query)

        # Stage 2: Rank
        ranked = self.rank(hits)

        # Stage 3: Inject
        injection = self.inject(messages, ranked)

        # Stage 4: Generate
        if generate:
            response = await self.generate(injection.messages)
        else:
            response = ""

        elapsed_ms = (time.monotonic() - start) * 1000

        return RAGResult(
            response=response,
            memories_used=ranked,
            query=query,
            search_hits=len(hits),
            memories_ranked=len(ranked),
            memories_injected=injection.memories_injected,
            tokens_used=injection.tokens_used,
            pipeline_time_ms=round(elapsed_ms, 2),
        )

    async def enhance_context(
        self,
        messages: list[dict[str, str]],
        query: str,
    ) -> tuple[list[dict[str, str]], list[RankedMemory]]:
        """Search, rank, and inject memories without generation.

        Returns the enhanced message list and the memories used.
        This is the interface used by AgentCore to add memory context.
        """
        hits = await self.search(query)
        ranked = self.rank(hits)
        injection = self.inject(messages, ranked)
        return injection.messages, ranked
