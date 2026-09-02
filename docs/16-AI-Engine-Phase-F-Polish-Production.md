# AI Engine Phase F: Polish & Production

## Phase Overview

Phase F is the final phase — it wires everything together, optimizes performance, and prepares the AI engine for production use. This phase takes the individual components from Phases A-E and integrates them into a cohesive, tested, and documented system.

The Polish & Production phase transforms MYSTI from a collection of features into a production-ready AI engine.

---

## Goals and Success Criteria

### Primary Goals

1. **Wire everything together** — Integrate all components
2. **Optimize performance** — Cache, async, efficiency
3. **Full test suite** — Unit, integration, end-to-end
4. **Documentation** — API docs, architecture docs
5. **Production deployment** — Configuration, monitoring, logging
6. **Security hardening** — Audit, input validation, rate limiting

### Success Criteria

You know Phase F is complete when:

- All components are wired together
- Performance is optimized
- Full test suite passes
- Documentation is complete
- Production deployment works
- Security audit passes
- All existing tests still pass

---

## Architecture

### Current State (Phase A+B+C+D+E)

```
┌─────────────────────────────────────────────────┐
│  AgentCore                                       │
│  - Agent loop                                    │
│  - Task classification                           │
│  - Model routing                                 │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│  RAG Pipeline                                    │
│  - Memory retrieval                              │
│  - Context enhancement                           │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│  Tool Executor                                   │
│  - Tool calling                                  │
│  - Permission management                         │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│  Knowledge Integration                           │
│  - Entity extraction                             │
│  - Graph queries                                 │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│  Intelligence Layer                              │
│  - Proactive behavior                            │
│  - Auto-memory extraction                        │
│  - Streaming responses                           │
└─────────────────────────────────────────────────┘
```

**Problem:** Components exist but aren't fully integrated or optimized.

### Phase F Target State

```
┌─────────────────────────────────────────────────┐
│  Production AI Engine                            │
│                                                  │
│  ┌────────────────────────────────────────────┐ │
│  │  Configuration Management                  │ │
│  │  - Environment variables                   │ │
│  │  - Feature flags                           │ │
│  │  - Model configurations                    │ │
│  └───────────────────┬──────────────────────┘ │
│                      ↓                          │
│  ┌────────────────────────────────────────────┐ │
│  │  Caching Layer                             │ │
│  │  - LLM response cache                      │ │
│  │  - Knowledge graph cache                   │ │
│  │  - Memory search cache                     │ │
│  └───────────────────┬──────────────────────┘ │
│                      ↓                          │
│  ┌────────────────────────────────────────────┐ │
│  │  Performance Optimization                  │ │
│  │  - Async operations                        │ │
│  │  - Connection pooling                      │ │
│  │  - Resource limits                         │ │
│  └───────────────────┬──────────────────────┘ │
│                      ↓                          │
│  ┌────────────────────────────────────────────┐ │
│  │  Monitoring & Logging                      │ │
│  │  - Structured logging                      │ │
│  │  - Metrics collection                      │ │
│  │  - Error tracking                          │ │
│  └───────────────────┬──────────────────────┘ │
│                      ↓                          │
│  ┌────────────────────────────────────────────┐ │
│  │  Security Hardening                        │ │
│  │  - Input validation                        │ │
│  │  - Rate limiting                           │ │
│  │  - Audit logging                           │ │
│  └───────────────────┬──────────────────────┘ │
│                      ↓                          │
│  ┌────────────────────────────────────────────┐ │
│  │  Full Test Suite                           │ │
│  │  - Unit tests                              │ │
│  │  - Integration tests                       │ │
│  │  - End-to-end tests                        │ │
│  └────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

### Integration Flow

```
User Input
    ↓
┌─────────────────────────────────────────────┐
│  Configuration Check                         │
│  - Load config                               │
│  - Check feature flags                       │
│  - Validate environment                      │
└──────────────┬──────────────────────────────┘
               ↓
┌─────────────────────────────────────────────┐
│  Rate Limiting                               │
│  - Check user limits                         │
│  - Check system limits                       │
│  - Reject if exceeded                        │
└──────────────┬──────────────────────────────┘
               ↓
┌─────────────────────────────────────────────┐
│  Caching                                     │
│  - Check LLM cache                           │
│  - Check knowledge cache                     │
│  - Return cached if found                    │
└──────────────┬──────────────────────────────┘
               ↓
┌─────────────────────────────────────────────┐
│  Full AI Engine Pipeline                     │
│  (Phases A-E)                                │
└──────────────┬──────────────────────────────┘
               ↓
┌─────────────────────────────────────────────┐
│  Cache Results                               │
│  - Cache LLM response                        │
│  - Cache knowledge query                     │
│  - Update metrics                            │
└──────────────┬──────────────────────────────┘
               ↓
┌─────────────────────────────────────────────┐
│  Logging & Monitoring                        │
│  - Log request                               │
│  - Track metrics                             │
│  - Report errors                             │
└─────────────────────────────────────────────┘
```

---

## Implementation Details

### Step 1: Create Production Module Structure

Create the following files:

```
src/mysti/engine/
├── config.py
├── cache.py
├── rate_limiter.py
├── metrics.py
└── production.py
```

### Step 2: Implement ConfigManager (config.py)

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import os

@dataclass
class LLMConfig:
    model_id: str
    api_key: str
    api_base: str | None = None
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout: int = 30

@dataclass
class CacheConfig:
    enabled: bool = True
    ttl_seconds: int = 3600
    max_size: int = 1000
    backend: str = "memory"  # "memory", "redis"

@dataclass
class RateLimitConfig:
    enabled: bool = True
    requests_per_minute: int = 60
    tokens_per_minute: int = 100000

@dataclass
class LoggingConfig:
    level: str = "INFO"
    format: str = "json"
    file: str | None = None

@dataclass
class SecurityConfig:
    input_validation: bool = True
    max_input_length: int = 10000
    audit_logging: bool = True

@dataclass
class EngineConfig:
    llm: LLMConfig
    cache: CacheConfig
    rate_limit: RateLimitConfig
    logging: LoggingConfig
    security: SecurityConfig
    streaming: bool = True
    max_steps: int = 10

class ConfigManager:
    def __init__(self):
        self._config: EngineConfig | None = None

    def load_from_env(self) -> EngineConfig:
        self._config = EngineConfig(
            llm=LLMConfig(
                model_id=os.getenv("MYSTI_LLM_MODEL", "gpt-4o-mini"),
                api_key=os.getenv("MYSTI_LLM_API_KEY", ""),
                api_base=os.getenv("MYSTI_LLM_API_BASE"),
                max_tokens=int(os.getenv("MYSTI_LLM_MAX_TOKENS", "4096")),
                temperature=float(os.getenv("MYSTI_LLM_TEMPERATURE", "0.7")),
                timeout=int(os.getenv("MYSTI_LLM_TIMEOUT", "30")),
            ),
            cache=CacheConfig(
                enabled=os.getenv("MYSTI_CACHE_ENABLED", "true").lower() == "true",
                ttl_seconds=int(os.getenv("MYSTI_CACHE_TTL", "3600")),
                max_size=int(os.getenv("MYSTI_CACHE_MAX_SIZE", "1000")),
                backend=os.getenv("MYSTI_CACHE_BACKEND", "memory"),
            ),
            rate_limit=RateLimitConfig(
                enabled=os.getenv("MYSTI_RATE_LIMIT_ENABLED", "true").lower() == "true",
                requests_per_minute=int(os.getenv("MYSTI_RATE_LIMIT_RPM", "60")),
                tokens_per_minute=int(os.getenv("MYSTI_RATE_LIMIT_TPM", "100000")),
            ),
            logging=LoggingConfig(
                level=os.getenv("MYSTI_LOG_LEVEL", "INFO"),
                format=os.getenv("MYSTI_LOG_FORMAT", "json"),
                file=os.getenv("MYSTI_LOG_FILE"),
            ),
            security=SecurityConfig(
                input_validation=os.getenv("MYSTI_INPUT_VALIDATION", "true").lower() == "true",
                max_input_length=int(os.getenv("MYSTI_MAX_INPUT_LENGTH", "10000")),
                audit_logging=os.getenv("MYSTI_AUDIT_LOGGING", "true").lower() == "true",
            ),
            streaming=os.getenv("MYSTI_STREAMING", "true").lower() == "true",
            max_steps=int(os.getenv("MYSTI_MAX_STEPS", "10")),
        )
        return self._config

    def get_config(self) -> EngineConfig:
        if self._config is None:
            return self.load_from_env()
        return self._config

    def get_llm_config(self) -> LLMConfig:
        return self.get_config().llm

    def get_cache_config(self) -> CacheConfig:
        return self.get_config().cache

    def get_rate_limit_config(self) -> RateLimitConfig:
        return self.get_config().rate_limit
```

### Step 3: Implement Cache (cache.py)

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Protocol
import time
import hashlib
import json

class CacheBackend(Protocol):
    async def get(self, key: str) -> Any | None: ...
    async def set(self, key: str, value: Any, ttl: int) -> None: ...
    async def delete(self, key: str) -> None: ...
    async def clear(self) -> None: ...

@dataclass
class CacheEntry:
    key: str
    value: Any
    created_at: float
    ttl: int

class MemoryCacheBackend:
    def __init__(self, max_size: int = 1000):
        self._cache: dict[str, CacheEntry] = {}
        self._max_size = max_size

    async def get(self, key: str) -> Any | None:
        entry = self._cache.get(key)
        if entry is None:
            return None

        # Check if expired
        if time.time() - entry.created_at > entry.ttl:
            del self._cache[key]
            return None

        return entry.value

    async def set(self, key: str, value: Any, ttl: int) -> None:
        # Evict if at capacity
        if len(self._cache) >= self._max_size:
            # Remove oldest entry
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k].created_at)
            del self._cache[oldest_key]

        self._cache[key] = CacheEntry(
            key=key,
            value=value,
            created_at=time.time(),
            ttl=ttl,
        )

    async def delete(self, key: str) -> None:
        self._cache.pop(key, None)

    async def clear(self) -> None:
        self._cache.clear()

class LLMCache:
    def __init__(self, backend: CacheBackend, ttl: int = 3600):
        self._backend = backend
        self._ttl = ttl

    def _make_key(self, messages: list[dict], model_id: str, **kwargs: Any) -> str:
        # Create deterministic key from inputs
        content = json.dumps({
            "messages": messages,
            "model": model_id,
            **kwargs,
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()

    async def get(self, messages: list[dict], model_id: str, **kwargs: Any) -> str | None:
        key = self._make_key(messages, model_id, **kwargs)
        return await self._backend.get(key)

    async def set(self, messages: list[dict], model_id: str, response: str, **kwargs: Any) -> None:
        key = self._make_key(messages, model_id, **kwargs)
        await self._backend.set(key, response, self._ttl)

    async def invalidate(self, messages: list[dict], model_id: str, **kwargs: Any) -> None:
        key = self._make_key(messages, model_id, **kwargs)
        await self._backend.delete(key)

class KnowledgeCache:
    def __init__(self, backend: CacheBackend, ttl: int = 1800):
        self._backend = backend
        self._ttl = ttl

    async def get(self, query: str) -> Any | None:
        key = f"kg:{hashlib.sha256(query.encode()).hexdigest()}"
        return await self._backend.get(key)

    async def set(self, query: str, result: Any) -> None:
        key = f"kg:{hashlib.sha256(query.encode()).hexdigest()}"
        await self._backend.set(key, result, self._ttl)

class MemorySearchCache:
    def __init__(self, backend: CacheBackend, ttl: int = 900):
        self._backend = backend
        self._ttl = ttl

    async def get(self, query: str, limit: int) -> Any | None:
        key = f"mem:{hashlib.sha256(f'{query}:{limit}'.encode()).hexdigest()}"
        return await self._backend.get(key)

    async def set(self, query: str, limit: int, result: Any) -> None:
        key = f"mem:{hashlib.sha256(f'{query}:{limit}'.encode()).hexdigest()}"
        await self._backend.set(key, result, self._ttl)
```

### Step 4: Implement RateLimiter (rate_limiter.py)

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol
import time

class RateLimitBackend(Protocol):
    async def get_count(self, key: str, window: int) -> int: ...
    async def increment(self, key: str, window: int) -> int: ...

@dataclass
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    reset_at: float

class InMemoryRateLimitBackend:
    def __init__(self):
        self._counts: dict[str, list[float]] = {}

    async def get_count(self, key: str, window: int) -> int:
        now = time.time()
        cutoff = now - window

        if key not in self._counts:
            return 0

        # Remove old entries
        self._counts[key] = [t for t in self._counts[key] if t > cutoff]
        return len(self._counts[key])

    async def increment(self, key: str, window: int) -> int:
        now = time.time()
        cutoff = now - window

        if key not in self._counts:
            self._counts[key] = []

        # Remove old entries
        self._counts[key] = [t for t in self._counts[key] if t > cutoff]

        # Add new entry
        self._counts[key].append(now)

        return len(self._counts[key])

class RateLimiter:
    def __init__(
        self,
        backend: RateLimitBackend,
        requests_per_minute: int = 60,
        tokens_per_minute: int = 100000,
    ):
        self._backend = backend
        self._rpm = requests_per_minute
        self._tpm = tokens_per_minute

    async def check_rate_limit(self, user_id: str) -> RateLimitResult:
        # Check request rate
        request_count = await self._backend.get_count(f"req:{user_id}", 60)
        if request_count >= self._rpm:
            return RateLimitResult(
                allowed=False,
                limit=self._rpm,
                remaining=0,
                reset_at=time.time() + 60,
            )

        # Increment request count
        new_count = await self._backend.increment(f"req:{user_id}", 60)

        return RateLimitResult(
            allowed=True,
            limit=self._rpm,
            remaining=self._rpm - new_count,
            reset_at=time.time() + 60,
        )

    async def check_token_rate_limit(self, user_id: str, tokens: int) -> RateLimitResult:
        # Check token rate
        token_count = await self._backend.get_count(f"tokens:{user_id}", 60)
        if token_count + tokens > self._tpm:
            return RateLimitResult(
                allowed=False,
                limit=self._tpm,
                remaining=max(0, self._tpm - token_count),
                reset_at=time.time() + 60,
            )

        # Increment token count
        new_count = await self._backend.increment(f"tokens:{user_id}", 60)

        return RateLimitResult(
            allowed=True,
            limit=self._tpm,
            remaining=self._tpm - new_count,
            reset_at=time.time() + 60,
        )
```

### Step 5: Implement Metrics (metrics.py)

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Protocol
import time
from collections import defaultdict

class MetricsBackend(Protocol):
    async def increment(self, name: str, tags: dict[str, str]) -> None: ...
    async def gauge(self, name: str, value: float, tags: dict[str, str]) -> None: ...
    async def timing(self, name: str, duration_ms: float, tags: dict[str, str]) -> None: ...

@dataclass
class Metric:
    name: str
    value: float
    metric_type: str  # "counter", "gauge", "timing"
    tags: dict[str, str]
    timestamp: float

class InMemoryMetricsBackend:
    def __init__(self):
        self._metrics: list[Metric] = []
        self._counters: dict[str, int] = defaultdict(int)
        self._gauges: dict[str, float] = {}

    async def increment(self, name: str, tags: dict[str, str]) -> None:
        key = f"{name}:{tags}"
        self._counters[key] += 1
        self._metrics.append(Metric(
            name=name,
            value=self._counters[key],
            metric_type="counter",
            tags=tags,
            timestamp=time.time(),
        ))

    async def gauge(self, name: str, value: float, tags: dict[str, str]) -> None:
        key = f"{name}:{tags}"
        self._gauges[key] = value
        self._metrics.append(Metric(
            name=name,
            value=value,
            metric_type="gauge",
            tags=tags,
            timestamp=time.time(),
        ))

    async def timing(self, name: str, duration_ms: float, tags: dict[str, str]) -> None:
        self._metrics.append(Metric(
            name=name,
            value=duration_ms,
            metric_type="timing",
            tags=tags,
            timestamp=time.time(),
        ))

class MetricsCollector:
    def __init__(self, backend: MetricsBackend):
        self._backend = backend

    async def track_request(self, session_id: str, endpoint: str) -> None:
        await self._backend.increment("requests.total", {
            "session": session_id,
            "endpoint": endpoint,
        })

    async def track_llm_call(self, model_id: str, latency_ms: float, tokens: int) -> None:
        await self._backend.timing("llm.latency", latency_ms, {"model": model_id})
        await self._backend.increment("llm.calls", {"model": model_id})
        await self._backend.gauge("llm.tokens", float(tokens), {"model": model_id})

    async def track_tool_call(self, tool_name: str, success: bool) -> None:
        await self._backend.increment("tools.calls", {
            "tool": tool_name,
            "success": str(success),
        })

    async def track_memory_search(self, query_time_ms: float, results: int) -> None:
        await self._backend.timing("memory.search_time", query_time_ms, {})
        await self._backend.gauge("memory.results", float(results), {})

    async def track_error(self, error_type: str, component: str) -> None:
        await self._backend.increment("errors.total", {
            "type": error_type,
            "component": component,
        })

    async def track_cache_hit(self, cache_type: str) -> None:
        await self._backend.increment("cache.hits", {"type": cache_type})

    async def track_cache_miss(self, cache_type: str) -> None:
        await self._backend.increment("cache.misses", {"type": cache_type})
```

### Step 6: Implement ProductionEngine (production.py)

```python
from __future__ import annotations
from typing import Any, Protocol
import time
import logging
from .core import AgentCore, AgentResult
from .config import ConfigManager, EngineConfig
from .cache import MemoryCacheBackend, LLMCache, KnowledgeCache, MemorySearchCache
from .rate_limiter import InMemoryRateLimitBackend, RateLimiter
from .metrics import InMemoryMetricsBackend, MetricsCollector

logger = logging.getLogger(__name__)

class ProductionEngine:
    def __init__(self, config: EngineConfig | None = None):
        # Load config
        self.config_manager = ConfigManager()
        self.config = config or self.config_manager.load_from_env()

        # Initialize backends
        self.cache_backend = MemoryCacheBackend(max_size=self.config.cache.max_size)
        self.rate_limit_backend = InMemoryRateLimitBackend()
        self.metrics_backend = InMemoryMetricsBackend()

        # Initialize caches
        self.llm_cache = LLMCache(backend=self.cache_backend, ttl=self.config.cache.ttl_seconds)
        self.knowledge_cache = KnowledgeCache(backend=self.cache_backend, ttl=1800)
        self.memory_cache = MemorySearchCache(backend=self.cache_backend, ttl=900)

        # Initialize rate limiter
        self.rate_limiter = RateLimiter(
            backend=self.rate_limit_backend,
            requests_per_minute=self.config.rate_limit.requests_per_minute,
            tokens_per_minute=self.config.rate_limit.tokens_per_minute,
        )

        # Initialize metrics
        self.metrics = MetricsCollector(backend=self.metrics_backend)

        # Initialize core engine (will be set via set_engine)
        self._engine: AgentCore | None = None

        # Configure logging
        self._setup_logging()

    def _setup_logging(self) -> None:
        level = getattr(logging, self.config.logging.level.upper(), logging.INFO)
        logging.basicConfig(
            level=level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            filename=self.config.logging.file,
        )

    def set_engine(self, engine: AgentCore) -> None:
        self._engine = engine

    async def chat(self, session_id: str, user_id: str, message: str) -> AgentResult:
        if not self._engine:
            raise RuntimeError("Engine not initialized. Call set_engine() first.")

        start_time = time.time()

        try:
            # 1. Rate limiting
            if self.config.rate_limit.enabled:
                rate_limit_result = await self.rate_limiter.check_rate_limit(user_id)
                if not rate_limit_result.allowed:
                    raise Exception(f"Rate limit exceeded. Try again in {rate_limit_result.remaining}s")

            # 2. Input validation
            if self.config.security.input_validation:
                if len(message) > self.config.security.max_input_length:
                    raise Exception(f"Input too long. Max {self.config.security.max_input_length} characters")

            # 3. Check cache
            if self.config.cache.enabled:
                cached_response = await self.llm_cache.get(
                    messages=[{"role": "user", "content": message}],
                    model_id=self.config.llm.model_id,
                )
                if cached_response:
                    await self.metrics.track_cache_hit("llm")
                    return AgentResult(
                        session_id=session_id,
                        response=cached_response,
                        messages=[],
                        steps=[],
                        total_tokens=0,
                        tools_used=[],
                        memories_used=[],
                        metadata={"cached": True},
                    )
                await self.metrics.track_cache_miss("llm")

            # 4. Execute engine
            result = await self._engine.chat(session_id, message)

            # 5. Cache response
            if self.config.cache.enabled and result.response:
                await self.llm_cache.set(
                    messages=[{"role": "user", "content": message}],
                    model_id=self.config.llm.model_id,
                    response=result.response,
                )

            # 6. Track metrics
            latency_ms = (time.time() - start_time) * 1000
            await self.metrics.track_request(session_id, "/chat")
            await self.metrics.track_llm_call(
                model_id=self.config.llm.model_id,
                latency_ms=latency_ms,
                tokens=result.total_tokens,
            )

            # 7. Audit logging
            if self.config.security.audit_logging:
                logger.info(
                    "Chat request",
                    session_id=session_id,
                    user_id=user_id,
                    message_length=len(message),
                    latency_ms=latency_ms,
                    tokens=result.total_tokens,
                )

            return result

        except Exception as e:
            await self.metrics.track_error(type(e).__name__, "chat")
            logger.error(f"Chat error: {e}")
            raise

    async def chat_stream(self, session_id: str, user_id: str, message: str):
        if not self._engine:
            raise RuntimeError("Engine not initialized. Call set_engine() first.")

        # Rate limiting
        if self.config.rate_limit.enabled:
            rate_limit_result = await self.rate_limiter.check_rate_limit(user_id)
            if not rate_limit_result.allowed:
                raise Exception(f"Rate limit exceeded")

        # Stream from engine
        async for chunk in self._engine.chat_stream(session_id, message):
            yield chunk

    async def get_metrics(self) -> dict[str, Any]:
        return {
            "total_requests": len(self.metrics_backend._metrics),
            "counters": dict(self.metrics_backend._counters),
            "gauges": dict(self.metrics_backend._gauges),
        }

    async def clear_cache(self) -> None:
        await self.cache_backend.clear()

    async def get_health(self) -> dict[str, str]:
        return {
            "status": "healthy",
            "engine": "initialized" if self._engine else "not_initialized",
            "cache": "enabled" if self.config.cache.enabled else "disabled",
            "rate_limit": "enabled" if self.config.rate_limit.enabled else "disabled",
        }
```

### Step 7: Update AgentCore for Production

Update `src/mysti/engine/core.py`:

```python
class AgentCore:
    def __init__(
        self,
        llm: LLMClient,
        tools: ToolGateway | None = None,
        memory: MemoryService | None = None,
        rag: RAGPipeline | None = None,
        knowledge_graph: KnowledgeGraph | None = None,
        permission_manager: PermissionManager | None = None,
        audit_log: AuditLog | None = None,
        max_steps: int = 10,
        streaming: bool = True,
    ):
        # ... existing initialization ...

        # Initialize all components (from Phases A-E)
        self.task_classifier = TaskClassifier(llm=llm)
        self.model_router = ModelRouter()
        self.entity_extractor = EntityExtractor(llm=llm, knowledge_graph=knowledge_graph)
        self.graph_query = GraphQuery(knowledge_graph=knowledge_graph) if knowledge_graph else None
        self.proactive_engine = ProactiveEngine(memory=memory, knowledge_graph=knowledge_graph)
        self.auto_memory = AutoMemoryExtractor(llm=llm, memory=memory)

        # Configuration
        self.max_steps = max_steps
        self.streaming = streaming

    async def chat(self, session_id: str, message: str) -> AgentResult:
        # Full pipeline with all components
        # ... complete implementation ...

    async def chat_stream(self, session_id: str, message: str):
        # Streaming pipeline with all components
        # ... complete implementation ...
```

---

## Testing

### Unit Tests

**test_config.py:**

```python
import pytest
from mysti.engine.config import ConfigManager

def test_load_from_env():
    manager = ConfigManager()
    config = manager.load_from_env()

    assert config.llm.model_id == "gpt-4o-mini"
    assert config.cache.enabled == True
    assert config.rate_limit.enabled == True
```

**test_cache.py:**

```python
import pytest
from mysti.engine.cache import MemoryCacheBackend, LLMCache

@pytest.mark.asyncio
async def test_cache_get_set():
    backend = MemoryCacheBackend()
    cache = LLMCache(backend=backend, ttl=60)

    # Set value
    await cache.set(
        messages=[{"role": "user", "content": "test"}],
        model_id="test-model",
        response="test response",
    )

    # Get value
    result = await cache.get(
        messages=[{"role": "user", "content": "test"}],
        model_id="test-model",
    )

    assert result == "test response"

@pytest.mark.asyncio
async def test_cache_expiry():
    backend = MemoryCacheBackend()
    cache = LLMCache(backend=backend, ttl=0)  # Immediate expiry

    await cache.set(
        messages=[{"role": "user", "content": "test"}],
        model_id="test-model",
        response="test response",
    )

    result = await cache.get(
        messages=[{"role": "user", "content": "test"}],
        model_id="test-model",
    )

    assert result is None
```

**test_rate_limiter.py:**

```python
import pytest
from mysti.engine.rate_limiter import InMemoryRateLimitBackend, RateLimiter

@pytest.mark.asyncio
async def test_rate_limit_within_bounds():
    backend = InMemoryRateLimitBackend()
    limiter = RateLimiter(backend=backend, requests_per_minute=10)

    result = await limiter.check_rate_limit("user1")

    assert result.allowed == True
    assert result.remaining == 9

@pytest.mark.asyncio
async def test_rate_limit_exceeded():
    backend = InMemoryRateLimitBackend()
    limiter = RateLimiter(backend=backend, requests_per_minute=2)

    # Make requests
    await limiter.check_rate_limit("user1")
    await limiter.check_rate_limit("user1")
    result = await limiter.check_rate_limit("user1")

    assert result.allowed == False
```

### Integration Tests

**test_production_engine.py:**

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from mysti.engine.production import ProductionEngine

@pytest.mark.asyncio
async def test_production_engine_initialization():
    engine = ProductionEngine()
    health = await engine.get_health()

    assert health["status"] == "healthy"
    assert health["engine"] == "not_initialized"

@pytest.mark.asyncio
async def test_rate_limiting():
    engine = ProductionEngine()
    # Mock engine
    mock_agent = AsyncMock()
    mock_agent.chat.return_value = AgentResult(
        session_id="test",
        response="test",
        messages=[],
        steps=[],
        total_tokens=100,
        tools_used=[],
        memories_used=[],
        metadata={},
    )
    engine.set_engine(mock_agent)

    # First request should succeed
    result = await engine.chat("session1", "user1", "test")
    assert result.response == "test"
```

---

## Deliverables

When Phase F is complete, you will have:

1. **`src/mysti/engine/config.py`** — ConfigManager class
2. **`src/mysti/engine/cache.py`** — LLMCache, KnowledgeCache, MemorySearchCache
3. **`src/mysti/engine/rate_limiter.py`** — RateLimiter class
4. **`src/mysti/engine/metrics.py`** — MetricsCollector class
5. **`src/mysti/engine/production.py`** — ProductionEngine class
6. **Updated AgentCore** — Full integration
7. **Tests** — 6+ unit tests, 2+ integration tests
8. **Documentation** — Architecture docs, API docs

---

## What Comes Next

After Phase F, the AI Engine is complete! You can:

1. **Deploy to production** — Use ProductionEngine for all requests
2. **Monitor performance** — Use metrics to track usage
3. **Scale** — Add Redis cache backend, external metrics
4. **Extend** — Add new tools, models, or behaviors

The AI Engine is now a complete, production-ready intelligence layer for MYSTI.

---

*Phase F completes the AI Engine — all components integrated, tested, and production-ready.*
