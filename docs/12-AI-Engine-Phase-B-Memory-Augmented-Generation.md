# AI Engine Phase B: Memory-Augmented Generation

## Phase Overview

Phase B builds the RAG (Retrieval-Augmented Generation) pipeline that retrieves relevant memories and injects them into the LLM context. Currently, the Agent Core from Phase A doesn't use memories during conversations. This phase makes MYSTI remember relevant information and use it when generating responses.

The RAG Pipeline transforms MYSTI from a chatbot that forgets into a personal AI that remembers and learns.

---

## Goals and Success Criteria

### Primary Goals

1. **Create RAGPipeline class** — Retrieve relevant memories based on user input
2. **Implement memory ranking** — Score and filter memories by relevance
3. **Implement memory injection** — Add memories to system prompt
4. **Add memory feedback loop** — Learn from user feedback on memory relevance
5. **Wire into AgentCore** — Use RAG during the Decide phase

### Success Criteria

You know Phase B is complete when:

- Relevant memories are retrieved during conversations
- Memories are ranked by relevance to the current query
- Memories are injected into the LLM context
- User can provide feedback on memory relevance
- AgentCore uses the RAG pipeline
- Memory retrieval doesn't significantly impact response time
- All existing tests still pass

---

## Architecture

### Current State (Phase A)

```
User Input
    ↓
AgentCore.chat()
    ↓
LLM.complete(messages)
    ↓
Response
```

**Problem:** No memory retrieval. The AI doesn't use stored memories.

### Phase B Target State

```
User Input
    ↓
AgentCore.chat()
    ↓
┌─────────────────────────────────────────┐
│           RAG Pipeline                  │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │ 1. Search                         │ │
│  │    Find relevant memories          │ │
│  └───────────────┬───────────────────┘ │
│                  ↓                      │
│  ┌───────────────────────────────────┐ │
│  │ 2. Rank                           │ │
│  │    Score by relevance              │ │
│  └───────────────┬───────────────────┘ │
│                  ↓                      │
│  ┌───────────────────────────────────┐ │
│  │ 3. Filter                         │ │
│  │    Remove low-relevance            │ │
│  └───────────────┬───────────────────┘ │
│                  ↓                      │
│  ┌───────────────────────────────────┐ │
│  │ 4. Inject                         │ │
│  │    Add to system prompt            │ │
│  └───────────────────────────────────┘ │
└─────────────────────────────────────────┘
    ↓
LLM.complete(messages_with_memories)
    ↓
Response
```

### RAG Pipeline Flow

```
User Query
    │
    ↓
┌─────────────────────────────────────────────┐
│              RAG Pipeline                    │
│                                              │
│  ┌────────────────────────────────────────┐ │
│  │ Step 1: Query Embedding                 │ │
│  │ - Generate embedding for user query     │ │
│  │ - Use EmbeddingService                  │ │
│  └───────────────────┬────────────────────┘ │
│                      ↓                       │
│  ┌────────────────────────────────────────┐ │
│  │ Step 2: Memory Search                   │ │
│  │ - Semantic search (cosine similarity)   │ │
│  │ - Keyword search (BM25)                 │ │
│  │ - Hybrid ranking                        │ │
│  └───────────────────┬────────────────────┘ │
│                      ↓                       │
│  ┌────────────────────────────────────────┐ │
│  │ Step 3: Memory Ranking                  │ │
│  │ - Score by relevance                    │ │
│  │ - Score by recency                      │ │
│  │ - Score by importance                   │ │
│  │ - Score by category match               │ │
│  └───────────────────┬────────────────────┘ │
│                      ↓                       │
│  ┌────────────────────────────────────────┐ │
│  │ Step 4: Memory Filtering                │ │
│  │ - Remove below threshold                │ │
│  │ - Limit to top N memories               │ │
│  │ - Deduplicate similar memories          │ │
│  └───────────────────┬────────────────────┘ │
│                      ↓                       │
│  ┌────────────────────────────────────────┐ │
│  │ Step 5: Context Injection               │ │
│  │ - Format memories for prompt            │ │
│  │ - Add to system message                 │ │
│  │ - Track tokens used                     │ │
│  └────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
    │
    ↓
Augmented Context
```

---

## Data Models

### MemoryContext

Represents the retrieved memories for a query.

```python
@dataclass
class MemoryContext:
    query: str
    query_embedding: list[float]
    memories: list[MemoryScore]
    total_tokens: int
    retrieval_time_ms: float
```

**Fields:**

- `query` — The original user query
- `query_embedding` — Embedding vector for the query
- `memories` — Ranked list of scored memories
- `total_tokens` — Estimated tokens used by memories
- `retrieval_time_ms` — Time taken for retrieval

### MemoryScore

A memory with its relevance score.

```python
@dataclass
class MemoryScore:
    memory_id: str
    content: str
    category: str
    relevance_score: float
    recency_score: float
    importance_score: float
    final_score: float
    metadata: dict[str, Any]
```

**Fields:**

- `memory_id` — Unique identifier
- `content` — Memory content
- `category` — Memory category
- `relevance_score` — Semantic similarity score (0-1)
- `recency_score` — How recent the memory is (0-1)
- `importance_score` — How important the memory is (0-1)
- `final_score` — Weighted combination of scores
- `metadata` — Additional metadata

### RAGConfig

Configuration for the RAG pipeline.

```python
@dataclass
class RAGConfig:
    max_memories: int = 5
    min_relevance_threshold: float = 0.3
    relevance_weight: float = 0.5
    recency_weight: float = 0.2
    importance_weight: float = 0.3
    max_context_tokens: int = 2000
    enable_feedback: bool = True
```

**Fields:**

- `max_memories` — Maximum memories to inject
- `min_relevance_threshold` — Minimum relevance score to include
- `relevance_weight` — Weight for relevance in final score
- `recency_weight` — Weight for recency in final score
- `importance_weight` — Weight for importance in final score
- `max_context_tokens` — Maximum tokens for memory context
- `enable_feedback` — Whether to enable feedback learning

---

## API Design

### POST /agent/chat (Updated)

Now includes memory retrieval.

**Request:**

```json
{
  "session_id": "session-123",
  "message": "What's the status of my MYSTI project?",
  "context": {
    "use_memory": true,
    "memory_category": "projects"
  }
}
```

**Response:**

```json
{
  "session_id": "session-123",
  "response": "Your MYSTI project is in Phase B, building the RAG pipeline...",
  "memories_used": ["mem-001", "mem-002", "mem-003"],
  "memory_context": {
    "query": "What's the status of my MYSTI project?",
    "memories_count": 3,
    "retrieval_time_ms": 45
  }
}
```

### GET /agent/memory-context/{session_id}

Get the memories used in the last response.

**Response:**

```json
{
  "session_id": "session-123",
  "query": "What's the status of my MYSTI project?",
  "memories": [
    {
      "memory_id": "mem-001",
      "content": "MYSTI is in Phase B, building RAG pipeline",
      "category": "projects",
      "relevance_score": 0.89,
      "recency_score": 0.95,
      "importance_score": 0.8,
      "final_score": 0.88
    }
  ]
}
```

### POST /agent/memory-feedback

Provide feedback on memory relevance.

**Request:**

```json
{
  "session_id": "session-123",
  "memory_id": "mem-001",
  "feedback": "relevant",
  "query": "What's the status of my MYSTI project?"
}
```

**Response:**

```json
{
  "status": "recorded",
  "memory_id": "mem-001",
  "feedback": "relevant"
}
```

---

## Implementation Details

### Step 1: Create RAG Module Structure

Create the following files:

```
src/mysti/engine/
├── rag.py
├── memory_ranker.py
└── memory_injector.py
```

### Step 2: Implement MemoryRanker (memory_ranker.py)

```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

@dataclass
class MemoryScore:
    memory_id: str
    content: str
    category: str
    relevance_score: float
    recency_score: float
    importance_score: float
    final_score: float
    metadata: dict[str, Any]

class MemoryRanker:
    def __init__(
        self,
        relevance_weight: float = 0.5,
        recency_weight: float = 0.2,
        importance_weight: float = 0.3,
    ):
        self.relevance_weight = relevance_weight
        self.recency_weight = recency_weight
        self.importance_weight = importance_weight

    def calculate_recency_score(self, created_at: str) -> float:
        try:
            created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            now = datetime.now(UTC)
            days_old = (now - created).days
            # Exponential decay: score halves every 30 days
            return max(0.0, 2 ** (-days_old / 30))
        except (ValueError, TypeError):
            return 0.5  # Default score for invalid dates

    def calculate_importance_score(self, importance: float | None) -> float:
        if importance is None:
            return 0.5
        return max(0.0, min(1.0, importance))

    def rank_memories(
        self,
        memories: list[dict[str, Any]],
        query_embedding: list[float] | None = None,
    ) -> list[MemoryScore]:
        scored = []
        for mem in memories:
            relevance = mem.get("relevance_score", 0.5)
            recency = self.calculate_recency_score(mem.get("created_at", ""))
            importance = self.calculate_importance_score(mem.get("importance"))

            final_score = (
                self.relevance_weight * relevance +
                self.recency_weight * recency +
                self.importance_weight * importance
            )

            scored.append(MemoryScore(
                memory_id=mem.get("id", ""),
                content=mem.get("content", ""),
                category=mem.get("category", "general"),
                relevance_score=relevance,
                recency_score=recency,
                importance_score=importance,
                final_score=final_score,
                metadata=mem.get("metadata", {})
            ))

        # Sort by final score descending
        scored.sort(key=lambda x: x.final_score, reverse=True)
        return scored

    def filter_memories(
        self,
        scored_memories: list[MemoryScore],
        min_threshold: float = 0.3,
        max_count: int = 5,
    ) -> list[MemoryScore]:
        filtered = [m for m in scored_memories if m.final_score >= min_threshold]
        return filtered[:max_count]

    def deduplicate_memories(
        self,
        memories: list[MemoryScore],
        similarity_threshold: float = 0.9,
    ) -> list[MemoryScore]:
        if not memories:
            return []

        unique = [memories[0]]
        for mem in memories[1:]:
            is_duplicate = False
            for existing in unique:
                # Simple content similarity (could use embeddings for better results)
                if self._content_similarity(mem.content, existing.content) > similarity_threshold:
                    is_duplicate = True
                    break
            if not is_duplicate:
                unique.append(mem)
        return unique

    def _content_similarity(self, a: str, b: str) -> float:
        # Simple Jaccard similarity
        words_a = set(a.lower().split())
        words_b = set(b.lower().split())
        if not words_a or not words_b:
            return 0.0
        intersection = words_a & words_b
        union = words_a | words_b
        return len(intersection) / len(union)
```

### Step 3: Implement MemoryInjector (memory_injector.py)

```python
from __future__ import annotations
from typing import Any

class MemoryInjector:
    def __init__(self, max_context_tokens: int = 2000):
        self.max_context_tokens = max_context_tokens

    def format_memories(self, memories: list[Any]) -> str:
        if not memories:
            return ""

        lines = ["## Relevant Memories\n"]
        token_count = 0

        for mem in memories:
            content = mem.content if hasattr(mem, "content") else mem.get("content", "")
            category = mem.category if hasattr(mem, "category") else mem.get("category", "general")
            score = mem.final_score if hasattr(mem, "final_score") else mem.get("final_score", 0.0)

            line = f"- [{category}] {content} (relevance: {score:.2f})"
            estimated_tokens = len(line.split())

            if token_count + estimated_tokens > self.max_context_tokens:
                break

            lines.append(line)
            token_count += estimated_tokens

        return "\n".join(lines)

    def inject_into_messages(
        self,
        messages: list[dict[str, str]],
        memories: list[Any],
    ) -> list[dict[str, str]]:
        if not memories:
            return messages

        memory_context = self.format_memories(memories)
        if not memory_context:
            return messages

        # Find system message and inject memories
        enhanced_messages = []
        for msg in messages:
            if msg["role"] == "system":
                enhanced_content = msg["content"] + "\n\n" + memory_context
                enhanced_messages.append({
                    "role": "system",
                    "content": enhanced_content
                })
            else:
                enhanced_messages.append(msg)

        return enhanced_messages

    def estimate_tokens(self, memories: list[Any]) -> int:
        total = 0
        for mem in memories:
            content = mem.content if hasattr(mem, "content") else mem.get("content", "")
            total += len(content.split())
        return total
```

### Step 4: Implement RAGPipeline (rag.py)

```python
from __future__ import annotations
import asyncio
from dataclasses import dataclass
from typing import Any, Protocol

class EmbeddingService(Protocol):
    async def generate_embedding(self, text: str) -> list[float]: ...
    async def similarity_score(self, a: list[float], b: list[float]) -> float: ...

class MemoryService(Protocol):
    async def search(self, query: str, category: str | None = None) -> list[Any]: ...

@dataclass
class RAGConfig:
    max_memories: int = 5
    min_relevance_threshold: float = 0.3
    relevance_weight: float = 0.5
    recency_weight: float = 0.2
    importance_weight: float = 0.3
    max_context_tokens: int = 2000
    enable_feedback: bool = True

class RAGPipeline:
    def __init__(
        self,
        memory_service: MemoryService,
        embedding_service: EmbeddingService,
        config: RAGConfig | None = None,
    ):
        self.memory = memory_service
        self.embeddings = embedding_service
        self.config = config or RAGConfig()
        self.ranker = MemoryRanker(
            relevance_weight=self.config.relevance_weight,
            recency_weight=self.config.recency_weight,
            importance_weight=self.config.importance_weight,
        )
        self.injector = MemoryInjector(max_context_tokens=self.config.max_context_tokens)
        self._feedback: dict[str, list[dict]] = {}

    async def retrieve(
        self,
        query: str,
        category: str | None = None,
    ) -> list[Any]:
        # Search for relevant memories
        memories = await self.memory.search(query, category)

        if not memories:
            return []

        # Rank memories
        scored = self.ranker.rank_memories(memories)

        # Filter by threshold and limit
        filtered = self.ranker.filter_memories(
            scored,
            min_threshold=self.config.min_relevance_threshold,
            max_count=self.config.max_memories,
        )

        # Deduplicate
        unique = self.ranker.deduplicate_memories(filtered)

        return unique

    async def enhance_context(
        self,
        messages: list[dict[str, str]],
        query: str,
        category: str | None = None,
    ) -> tuple[list[dict[str, str]], list[Any]]:
        memories = await self.retrieve(query, category)
        enhanced_messages = self.injector.inject_into_messages(messages, memories)
        return enhanced_messages, memories

    def record_feedback(
        self,
        memory_id: str,
        feedback: str,
        query: str,
    ) -> None:
        if memory_id not in self._feedback:
            self._feedback[memory_id] = []

        self._feedback[memory_id].append({
            "feedback": feedback,
            "query": query,
            "timestamp": asyncio.get_event_loop().time()
        })

    def get_feedback_stats(self, memory_id: str) -> dict[str, int]:
        if memory_id not in self._feedback:
            return {"relevant": 0, "irrelevant": 0}

        feedbacks = self._feedback[memory_id]
        return {
            "relevant": sum(1 for f in feedbacks if f["feedback"] == "relevant"),
            "irrelevant": sum(1 for f in feedbacks if f["feedback"] == "irrelevant"),
        }
```

### Step 5: Wire into AgentCore

Update `src/mysti/engine/core.py`:

```python
class AgentCore:
    def __init__(
        self,
        llm: LLMClient,
        tools: ToolGateway | None = None,
        memory: MemoryService | None = None,
        rag: RAGPipeline | None = None,
        max_steps: int = 10,
    ):
        self.llm = llm
        self.tools = tools
        self.memory = memory
        self.rag = rag
        self.max_steps = max_steps
        self._states: dict[str, AgentState] = {}

    async def chat(self, session_id: str, message: str) -> AgentResult:
        state = self.get_state(session_id)
        state.add_message("user", message)

        steps = []
        total_tokens = 0

        # Retrieve relevant memories
        memories_used = []
        if self.rag:
            enhanced_messages, memories = await self.rag.enhance_context(
                state.to_context_messages(),
                message
            )
            memories_used = [m.memory_id for m in memories]
            state.memories_used.extend(memories_used)
        else:
            enhanced_messages = state.to_context_messages()

        # Build system prompt
        prompt_builder = DynamicPromptBuilder()
        system_prompt = prompt_builder.build()
        messages = [{"role": "system", "content": system_prompt}] + enhanced_messages

        # Call LLM
        step_start = asyncio.get_event_loop().time()
        response = await self.llm.complete(messages)
        step_duration = (asyncio.get_event_loop().time() - step_start) * 1000

        state.add_message("assistant", response)

        steps.append(AgentStep(
            step_number=1,
            input_text=message,
            action=AgentAction(action_type="respond", reasoning="LLM response with memory context"),
            output_text=response,
            tool_results=[],
            memories_retrieved=memories_used,
            duration_ms=step_duration,
            tokens_used=len(response.split())
        ))

        return AgentResult(
            response=response,
            steps=steps,
            total_tokens=len(response.split()),
            total_duration_ms=step_duration,
            tools_used=[],
            memories_used=memories_used,
            loop_terminated="normal"
        )
```

---

## Dependencies

### New Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| `numpy` | >=1.26 | Vector operations for similarity |
| `scikit-learn` | >=1.4 | Cosine similarity (optional) |

### Existing Dependencies Used

| Dependency | Purpose |
|------------|---------|
| `memory/service.py` | Memory search |
| `memory/embeddings.py` | Embedding generation |
| `memory/models.py` | Memory data models |

---

## Testing

### Unit Tests

**test_memory_ranker.py:**

```python
import pytest
from datetime import UTC, datetime, timedelta
from mysti.engine.memory_ranker import MemoryRanker, MemoryScore

def test_rank_memories():
    ranker = MemoryRanker()
    memories = [
        {"id": "1", "content": "Test memory 1", "category": "general", "relevance_score": 0.8, "created_at": datetime.now(UTC).isoformat()},
        {"id": "2", "content": "Test memory 2", "category": "projects", "relevance_score": 0.6, "created_at": (datetime.now(UTC) - timedelta(days=30)).isoformat()},
    ]
    scored = ranker.rank_memories(memories)
    assert len(scored) == 2
    assert scored[0].final_score >= scored[1].final_score

def test_filter_memories():
    ranker = MemoryRanker()
    scored = [
        MemoryScore("1", "High", "general", 0.9, 0.9, 0.9, 0.9, {}),
        MemoryScore("2", "Low", "general", 0.2, 0.2, 0.2, 0.2, {}),
    ]
    filtered = ranker.filter_memories(scored, min_threshold=0.5)
    assert len(filtered) == 1
    assert filtered[0].memory_id == "1"

def test_deduplicate_memories():
    ranker = MemoryRanker()
    memories = [
        MemoryScore("1", "Hello world test", "general", 0.8, 0.8, 0.8, 0.8, {}),
        MemoryScore("2", "Hello world test again", "general", 0.7, 0.7, 0.7, 0.7, {}),
        MemoryScore("3", "Completely different", "general", 0.6, 0.6, 0.6, 0.6, {}),
    ]
    unique = ranker.deduplicate_memories(memories, similarity_threshold=0.9)
    assert len(unique) == 2  # First two are similar, third is different
```

**test_memory_injector.py:**

```python
import pytest
from mysti.engine.memory_injector import MemoryInjector

def test_format_memories():
    injector = MemoryInjector()
    memories = [
        type('Memory', (), {"content": "Test content", "category": "general", "final_score": 0.8})(),
    ]
    formatted = injector.format_memories(memories)
    assert "Relevant Memories" in formatted
    assert "Test content" in formatted

def test_inject_into_messages():
    injector = MemoryInjector()
    messages = [
        {"role": "system", "content": "You are MYSTI."},
        {"role": "user", "content": "Hello"}
    ]
    memories = [
        type('Memory', (), {"content": "User likes Python", "category": "preferences", "final_score": 0.9})(),
    ]
    injected = injector.inject_into_messages(messages, memories)
    assert len(injected) == 2
    assert "User likes Python" in injected[0]["content"]
```

**test_rag_pipeline.py:**

```python
import pytest
from unittest.mock import AsyncMock
from mysti.engine.rag import RAGPipeline, RAGConfig

@pytest.mark.asyncio
async def test_rag_retrieve():
    mock_memory = AsyncMock()
    mock_memory.search.return_value = [
        {"id": "1", "content": "Test memory", "category": "general", "relevance_score": 0.8, "created_at": "2026-09-02T00:00:00Z"}
    ]
    mock_embeddings = AsyncMock()

    rag = RAGPipeline(mock_memory, mock_embeddings)
    results = await rag.retrieve("test query")

    assert len(results) == 1
    assert results[0].memory_id == "1"

@pytest.mark.asyncio
async def test_rag_enhance_context():
    mock_memory = AsyncMock()
    mock_memory.search.return_value = [
        {"id": "1", "content": "User prefers dark mode", "category": "preferences", "relevance_score": 0.9, "created_at": "2026-09-02T00:00:00Z"}
    ]
    mock_embeddings = AsyncMock()

    rag = RAGPipeline(mock_memory, mock_embeddings)
    messages = [{"role": "system", "content": "You are MYSTI."}]
    enhanced, memories = await rag.enhance_context(messages, "What's my preference?")

    assert len(enhanced) == 2  # system + user
    assert "User prefers dark mode" in enhanced[0]["content"]
    assert len(memories) == 1
```

### Integration Tests

**test_rag_integration.py:**

```python
import pytest
from mysti.engine.rag import RAGPipeline
from mysti.memory.service import MemoryService
from mysti.memory.embeddings import EmbeddingService

@pytest.mark.asyncio
async def test_rag_with_real_memory_service():
    # This would use real services in integration tests
    # For now, test the flow
    pass
```

---

## Edge Cases

### No Memories Found

```python
async def retrieve(self, query: str, category: str | None = None) -> list[Any]:
    memories = await self.memory.search(query, category)
    if not memories:
        return []  # Return empty list, don't error
    # Continue with ranking...
```

### All Memories Below Threshold

```python
def filter_memories(self, scored_memories, min_threshold, max_count):
    filtered = [m for m in scored_memories if m.final_score >= min_threshold]
    if not filtered:
        # Return top N memories even if below threshold
        return scored_memories[:max_count]
    return filtered[:max_count]
```

### Context Window Exceeded

```python
def inject_into_messages(self, messages, memories):
    memory_context = self.format_memories(memories)
    if not memory_context:
        return messages

    # Check if adding memories would exceed context limit
    estimated_tokens = self.estimate_tokens(memories)
    if estimated_tokens > self.max_context_tokens:
        # Truncate memories
        memories = memories[:len(memories) // 2]
        memory_context = self.format_memories(memories)

    # Continue with injection...
```

### Memory Search Fails

```python
async def retrieve(self, query, category=None):
    try:
        memories = await self.memory.search(query, category)
    except Exception:
        # Fallback to no memories
        return []
    # Continue with ranking...
```

### Feedback Loop Overflow

```python
def record_feedback(self, memory_id, feedback, query):
    if memory_id not in self._feedback:
        self._feedback[memory_id] = []

    # Limit feedback history per memory
    if len(self._feedback[memory_id]) > 100:
        self._feedback[memory_id] = self._feedback[memory_id][-50:]

    self._feedback[memory_id].append({...})
```

---

## Deliverables

When Phase B is complete, you will have:

1. **`src/mysti/engine/rag.py`** — RAGPipeline class
2. **`src/mysti/engine/memory_ranker.py`** — MemoryRanker class
3. **`src/mysti/engine/memory_injector.py`** — MemoryInjector class
4. **Updated AgentCore** — Uses RAG pipeline
5. **Updated API** — Memory context in responses
6. **Tests** — 8+ unit tests, 2+ integration tests

---

## What Comes Next

After Phase B, you will move to **Phase C: Tool Integration**, which adds:
- Tool calling during conversations
- Function calling support
- Tool permission checking
- Tool execution logging

Phase B's RAG pipeline provides the foundation for memory-aware tool calling, with relevant memories available when deciding which tools to use.

---

*Phase B makes MYSTI remember — retrieving relevant memories and using them in every conversation.*
