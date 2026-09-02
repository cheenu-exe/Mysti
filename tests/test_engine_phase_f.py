"""Tests for AI Engine Phase F: Polish & Production.

Covers:
- ConfigManager (env loading, defaults)
- LLMCache (get/set, TTL, eviction, stats)
- ProductionEngine (full pipeline, health, caching)
"""

from __future__ import annotations

import os
import time
from unittest.mock import AsyncMock

import pytest

from mysti.engine.cache import CacheStats, LLMCache
from mysti.engine.config import ConfigManager, EngineConfig, LLMConfig
from mysti.engine.production import HealthStatus, ProductionEngine


# ---- Helpers ----


class MockLLM:
    """Mock LLM for testing."""

    def __init__(self, response: str = "Hello from LLM") -> None:
        self._response = response
        self.call_count = 0

    async def complete(self, messages: list[dict[str, str]], **kwargs) -> str:
        self.call_count += 1
        return self._response


class MockMemory:
    """Mock memory service."""

    async def search(self, query: str, limit: int = 5) -> list:
        return []


# ---- ConfigManager tests ----


class TestConfigManager:
    def test_load_from_env(self):
        manager = ConfigManager()
        config = manager.load_from_env()
        assert isinstance(config, EngineConfig)
        assert config.llm.model_id == "gpt-4o-mini"

    def test_get_config_loads_if_needed(self):
        manager = ConfigManager()
        config = manager.get_config()
        assert isinstance(config, EngineConfig)

    def test_set_config(self):
        manager = ConfigManager()
        custom = EngineConfig(max_steps=5)
        manager.set_config(custom)
        assert manager.get_config().max_steps == 5

    def test_env_overrides(self, monkeypatch):
        monkeypatch.setenv("MYSTI_LLM_MODEL", "custom-model")
        monkeypatch.setenv("MYSTI_MAX_STEPS", "20")
        manager = ConfigManager()
        config = manager.load_from_env()
        assert config.llm.model_id == "custom-model"
        assert config.max_steps == 20

    def test_cache_config_from_env(self, monkeypatch):
        monkeypatch.setenv("MYSTI_CACHE_ENABLED", "false")
        monkeypatch.setenv("MYSTI_CACHE_TTL", "1800")
        manager = ConfigManager()
        config = manager.load_from_env()
        assert config.cache.enabled is False
        assert config.cache.ttl_seconds == 1800

    def test_rate_limit_config_from_env(self, monkeypatch):
        monkeypatch.setenv("MYSTI_RATE_LIMIT_RPM", "120")
        manager = ConfigManager()
        config = manager.load_from_env()
        assert config.rate_limit.requests_per_minute == 120


# ---- LLMCache tests ----


class TestLLMCache:
    def test_set_and_get(self):
        cache = LLMCache(max_size=10, ttl_seconds=60)
        messages = [{"role": "user", "content": "hello"}]
        cache.set(messages, "gpt-4o", "response")
        result = cache.get(messages, "gpt-4o")
        assert result == "response"

    def test_cache_miss(self):
        cache = LLMCache()
        result = cache.get([{"role": "user", "content": "hello"}], "gpt-4o")
        assert result is None

    def test_cache_hit_counted(self):
        cache = LLMCache()
        messages = [{"role": "user", "content": "hello"}]
        cache.set(messages, "gpt-4o", "response")
        cache.get(messages, "gpt-4o")
        assert cache.stats.hits == 1
        assert cache.stats.misses == 0

    def test_cache_miss_counted(self):
        cache = LLMCache()
        cache.get([{"role": "user", "content": "hello"}], "gpt-4o")
        assert cache.stats.misses == 1

    def test_ttl_expiry(self):
        cache = LLMCache(ttl_seconds=0)  # Immediate expiry
        messages = [{"role": "user", "content": "hello"}]
        cache.set(messages, "gpt-4o", "response")
        time.sleep(0.01)
        result = cache.get(messages, "gpt-4o")
        assert result is None

    def test_lru_eviction(self):
        cache = LLMCache(max_size=2)
        cache.set([{"role": "user", "content": "a"}], "m", "response_a")
        cache.set([{"role": "user", "content": "b"}], "m", "response_b")
        cache.set([{"role": "user", "content": "c"}], "m", "response_c")
        # 'a' should be evicted
        assert cache.get([{"role": "user", "content": "a"}], "m") is None
        assert cache.get([{"role": "user", "content": "b"}], "m") == "response_b"

    def test_invalidate_entry(self):
        cache = LLMCache()
        messages = [{"role": "user", "content": "hello"}]
        cache.set(messages, "gpt-4o", "response")
        removed = cache.invalidate(messages, "gpt-4o")
        assert removed is True
        assert cache.get(messages, "gpt-4o") is None

    def test_invalidate_not_found(self):
        cache = LLMCache()
        removed = cache.invalidate([{"role": "user", "content": "x"}], "m")
        assert removed is False

    def test_clear(self):
        cache = LLMCache()
        cache.set([{"role": "user", "content": "a"}], "m", "r")
        cache.clear()
        assert len(cache) == 0

    def test_stats(self):
        cache = LLMCache()
        cache.set([{"role": "user", "content": "a"}], "m", "r")
        cache.get([{"role": "user", "content": "a"}], "m")
        cache.get([{"role": "user", "content": "b"}], "m")
        stats = cache.stats
        assert stats.hits == 1
        assert stats.misses == 1
        assert stats.hit_rate == 0.5

    def test_len(self):
        cache = LLMCache()
        assert len(cache) == 0
        cache.set([{"role": "user", "content": "a"}], "m", "r")
        assert len(cache) == 1

    def test_hit_rate_zero_division(self):
        stats = CacheStats()
        assert stats.hit_rate == 0.0


# ---- ProductionEngine tests ----


class TestProductionEngine:
    @pytest.mark.asyncio
    async def test_basic_chat(self):
        llm = MockLLM(response="Hi there!")
        engine = ProductionEngine(llm=llm)
        result = await engine.chat("s1", "hello")
        assert result.response == "Hi there!"
        assert result.session_id == "s1"

    @pytest.mark.asyncio
    async def test_chat_caches_response(self):
        llm = MockLLM(response="cached response")
        engine = ProductionEngine(llm=llm)

        await engine.chat("s1", "hello")
        first_count = llm.call_count
        await engine.chat("s1", "hello")

        # Second call should use cache, so no additional LLM calls
        assert llm.call_count == first_count

    @pytest.mark.asyncio
    async def test_health_check(self):
        llm = MockLLM()
        engine = ProductionEngine(llm=llm)
        health = await engine.get_health()
        assert isinstance(health, HealthStatus)
        assert health.status in ("healthy", "degraded")
        assert "llm" in health.components

    @pytest.mark.asyncio
    async def test_cache_stats(self):
        llm = MockLLM()
        engine = ProductionEngine(llm=llm)
        await engine.chat("s1", "hello")
        stats = engine.get_cache_stats()
        assert "hits" in stats
        assert "misses" in stats

    @pytest.mark.asyncio
    async def test_cost_report(self):
        llm = MockLLM()
        engine = ProductionEngine(llm=llm)
        report = engine.get_cost_report()
        assert isinstance(report, dict)

    @pytest.mark.asyncio
    async def test_enhance_context(self):
        llm = MockLLM()
        memory = MockMemory()
        engine = ProductionEngine(llm=llm, memory=memory)
        messages = [{"role": "user", "content": "hello"}]
        enhanced, memories = await engine.enhance_context(messages, "hello")
        assert isinstance(enhanced, list)

    @pytest.mark.asyncio
    async def test_register_tool(self):
        llm = MockLLM()
        engine = ProductionEngine(llm=llm)

        async def my_tool(x: str = "default") -> str:
            return f"result: {x}"

        engine.register_tool(
            name="my_tool",
            func=my_tool,
            description="A test tool",
        )
        assert "my_tool" in engine.tool_registry

    @pytest.mark.asyncio
    async def test_close(self):
        llm = MockLLM()
        engine = ProductionEngine(llm=llm)
        await engine.close()  # Should not raise

    @pytest.mark.asyncio
    async def test_proactive_suggestions(self):
        llm = MockLLM()
        engine = ProductionEngine(llm=llm)
        suggestions = await engine.get_proactive_suggestions("help me", [])
        assert isinstance(suggestions, list)

    @pytest.mark.asyncio
    async def test_cache_disabled(self):
        from mysti.engine.config import CacheConfig
        llm = MockLLM(response="response")
        config = EngineConfig(cache=CacheConfig(enabled=False))
        engine = ProductionEngine(llm=llm, config=config)

        await engine.chat("s1", "hello")
        first_count = llm.call_count
        await engine.chat("s1", "hello")

        # With cache disabled, LLM should be called again
        assert llm.call_count > first_count
