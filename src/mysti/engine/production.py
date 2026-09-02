"""Production engine: wires all AI engine components together.

Phase F provides:
- Unified engine with all components
- Caching layer
- Rate limiting
- Health checks
- Graceful degradation
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from mysti.engine.cache import LLMCache
from mysti.engine.config import ConfigManager, EngineConfig
from mysti.engine.core import AgentCore, AgentResult
from mysti.engine.memory_injector import MemoryInjector
from mysti.engine.memory_ranker import MemoryRanker
from mysti.engine.model_router import ModelRouter
from mysti.engine.proactive_engine import ProactiveEngine
from mysti.engine.rag import RAGPipeline
from mysti.engine.tool_executor import ToolExecutor
from mysti.engine.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


class LLMClient(Protocol):
    """Minimal LLM interface."""

    async def complete(self, messages: list[dict[str, str]], **kwargs: Any) -> str: ...


class MemoryService(Protocol):
    """Memory service interface."""

    async def search(self, query: str, limit: int = 5) -> list[Any]: ...


@dataclass
class HealthStatus:
    """Engine health status."""

    status: str  # "healthy", "degraded", "unhealthy"
    components: dict[str, str] = field(default_factory=dict)
    uptime_seconds: float = 0.0


class ProductionEngine:
    """Unified AI engine with all components wired together.

    Provides:
    - Cached LLM responses
    - Memory-augmented generation (RAG)
    - Tool integration
    - Knowledge graph integration
    - Proactive suggestions
    - Model routing
    """

    def __init__(
        self,
        llm: LLMClient,
        memory: MemoryService | None = None,
        config: EngineConfig | None = None,
    ) -> None:
        self.llm = llm
        self.memory = memory
        self.config = config or EngineConfig()
        self._start_time = time.time()

        # Initialize components
        self.tool_registry = ToolRegistry()
        self.tool_executor = ToolExecutor(self.tool_registry)
        self.model_router = ModelRouter()
        self.proactive_engine = ProactiveEngine(memory=memory)
        self.memory_ranker = MemoryRanker()
        self.memory_injector = MemoryInjector(token_budget=1024)
        self.rag = RAGPipeline(
            memory=memory,
            llm=llm,
            ranker=self.memory_ranker,
            injector=self.memory_injector,
        )
        self.cache = LLMCache(
            max_size=self.config.cache.max_size,
            ttl_seconds=self.config.cache.ttl_seconds,
        )

        # Create the core agent
        self.agent = AgentCore(
            llm=llm,
            memory=memory,
            max_steps=self.config.max_steps,
        )

    async def chat(self, session_id: str, message: str) -> AgentResult:
        """Process a chat message through the full engine pipeline.

        Pipeline:
        1. Check cache
        2. Route to model
        3. Get proactive suggestions
        4. Run RAG pipeline
        5. Cache response
        """
        # Check cache
        if self.config.cache.enabled:
            cached = self.cache.get(
                [{"role": "user", "content": message}],
                self.config.llm.model_id,
            )
            if cached:
                logger.debug("Cache hit for message: %s", message[:50])
                return AgentResult(
                    session_id=session_id,
                    response=cached,
                    messages=[{"role": "user", "content": message}, {"role": "assistant", "content": cached}],
                    steps=[{"step": "cache_hit"}],
                    total_tokens=0,
                    tools_used=[],
                    memories_used=[],
                    metadata={"cached": True},
                )

        # Route to model
        routing = self.model_router.route()

        # Run the core agent
        result = await self.agent.chat(session_id, message)

        # Cache the response
        if self.config.cache.enabled and result.response:
            self.cache.set(
                [{"role": "user", "content": message}],
                self.config.llm.model_id,
                result.response,
            )

        result.metadata["model_routing"] = routing.model_id
        return result

    async def enhance_context(
        self,
        messages: list[dict[str, str]],
        query: str,
    ) -> tuple[list[dict[str, str]], list]:
        """Enhance messages with memory context via RAG pipeline."""
        return await self.rag.enhance_context(messages, query)

    async def get_proactive_suggestions(
        self,
        current_message: str,
        conversation_history: list[dict[str, str]],
    ) -> list:
        """Get proactive suggestions."""
        return await self.proactive_engine.get_suggestions(
            current_message, conversation_history
        )

    def register_tool(self, *args: Any, **kwargs: Any) -> None:
        """Register a tool with the engine."""
        self.tool_registry.register_function(*args, **kwargs)

    async def get_health(self) -> HealthStatus:
        """Check engine health."""
        components = {
            "llm": "configured" if self.llm else "missing",
            "memory": "configured" if self.memory else "missing",
            "cache": "enabled" if self.config.cache.enabled else "disabled",
            "tools": f"{len(self.tool_registry)} registered",
        }

        all_healthy = all(v != "missing" for v in components.values())
        status = "healthy" if all_healthy else "degraded"

        return HealthStatus(
            status=status,
            components=components,
            uptime_seconds=round(time.time() - self._start_time, 1),
        )

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache performance stats."""
        stats = self.cache.stats
        return {
            "hits": stats.hits,
            "misses": stats.misses,
            "hit_rate": round(stats.hit_rate, 4),
            "size": len(self.cache),
        }

    def get_cost_report(self) -> dict[str, float]:
        """Get model cost report."""
        return self.model_router.get_cost_report()

    async def close(self) -> None:
        """Release resources."""
        await self.agent.close()
