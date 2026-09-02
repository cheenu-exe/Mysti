# MYSTI AI Engine — Master Plan

## Executive Summary

The MYSTI AI Engine is the intelligence layer that transforms MYSTI from a memory storage system into a truly intelligent personal AI. It sits above the model layer, orchestrating memory, tools, knowledge, and reasoning to deliver context-aware, proactive assistance.

**Core Principle:** The LLM is a component, not the entire AI engine. MYSTI's intelligence comes from how it combines memory, tools, knowledge, and reasoning — not from any single model.

---

## What Exists vs What's Missing

### Already Built (Phases 0-8)

| Subsystem | Status | Maturity |
|-----------|--------|----------|
| Encryption (AES-256-GCM) | COMPLETE | High |
| Key hierarchy (master → category → record) | COMPLETE | High |
| Storage (local + S3) | COMPLETE | High |
| RAM cache (LRU + TTL) | COMPLETE | High |
| Memory service (store/search/suggest) | COMPLETE | High |
| Embeddings (3-tier fallback) | COMPLETE | High |
| Conversations (encrypted sessions) | COMPLETE | High |
| Summarization (LLM + extractive) | COMPLETE | High |
| Consolidation (dedup, merge, re-score) | COMPLETE | High |
| Research (5 connectors, relevance, briefings) | COMPLETE | High |
| Security (permissions, sandbox, injection) | COMPLETE | High |
| Tools (gateway + 6 tools) | COMPLETE | High |
| Knowledge graph + extraction | COMPLETE | Medium |
| Goals, projects, learning | COMPLETE | Medium |
| Model registry + benchmarks | COMPLETE | Medium |
| Voice, backup, notifications, export | COMPLETE | Medium |
| Web dashboard (Next.js) | COMPLETE | High |

### What's Missing for the AI Engine

| Missing Component | Impact | Priority |
|-------------------|--------|----------|
| Agent loop / orchestration | AI cannot decide what to do | CRITICAL |
| Tool integration in chat | AI cannot use tools during conversation | CRITICAL |
| Memory-augmented generation | AI doesn't use memories in responses | CRITICAL |
| Dynamic prompt construction | Hardcoded prompts, no context awareness | HIGH |
| Knowledge graph integration | Graph exists but is unused | HIGH |
| Model routing | Router exists but is unused | MEDIUM |
| Proactive behavior | AI never suggests or reminds | MEDIUM |
| Auto-memory extraction | AI doesn't learn from conversations | MEDIUM |
| Streaming responses | No real-time output | MEDIUM |
| Response post-processing | No output filtering | LOW |

---

## AI Engine Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        MYSTI AI Engine                           │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Intelligence Layer                     │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │   │
│  │  │ Model Router │  │ Proactive    │  │ Auto-Memory  │  │   │
│  │  │              │  │ Engine       │  │ Extractor    │  │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              ↑                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Agent Core                             │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐  │   │
│  │  │Understand│→ │  Decide  │→ │   Act    │→ │Respond │  │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └────────┘  │   │
│  └──────────────────────────────────────────────────────────┘   │
│           ↑              ↑              ↑              ↑         │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌──────────┐ │
│  │ RAG        │  │ Tool       │  │ Knowledge  │  │ Context  │ │
│  │ Pipeline   │  │ Gateway    │  │ Graph      │  │ Builder  │ │
│  └────────────┘  └────────────┘  └────────────┘  └──────────┘ │
│           ↑              ↑              ↑              ↑         │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Existing Systems                       │   │
│  │  Memory │ Research │ Security │ Tools │ Integration       │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Phase Overview

### Phase A: Agent Core
**The central orchestration loop**

The Agent Core is the "brain" that takes user input, decides what to do, and returns a response. It implements the Understand → Decide → Act → Respond cycle.

**Key deliverables:**
- `src/mysti/engine/core.py` — AgentCore class
- `src/mysti/engine/state.py` — AgentState, AgentStep models
- `src/mysti/engine/prompt.py` — DynamicPromptBuilder
- `src/mysti/engine/loop.py` — Main agent loop
- Updated CLI REPL with agent loop
- Updated API with agent endpoint

**Estimated effort:** 3-4 days

---

### Phase B: Memory-Augmented Generation
**RAG pipeline — retrieve relevant memories, inject into context**

The RAG Pipeline retrieves relevant memories based on user input and injects them into the LLM context. This makes MYSTI remember relevant information during conversations.

**Key deliverables:**
- `src/mysti/engine/rag.py` — RAGPipeline class
- `src/mysti/engine/memory_ranker.py` — MemoryRanker
- `src/mysti/engine/memory_injector.py` — MemoryInjector
- Memory feedback system
- Updated AgentCore with RAG integration

**Estimated effort:** 2-3 days

---

### Phase C: Tool Integration
**Wire tools into the agent — AI can call tools during conversation**

Tool Integration enables the AI to call tools (filesystem, browser, terminal, etc.) during conversations. This makes MYSTI actionable, not just conversational.

**Key deliverables:**
- `src/mysti/engine/tool_executor.py` — ToolExecutor class
- `src/mysti/engine/function_calling.py` — FunctionCalling support
- Updated AgentCore with tool integration
- Tool permission checking
- Tool execution logging

**Estimated effort:** 3-4 days

---

### Phase D: Knowledge Integration
**Wire knowledge graph + entity extraction into memory + chat**

Knowledge Integration makes the AI entity-aware. It extracts entities from conversations, stores them in the knowledge graph, and uses graph relationships for context.

**Key deliverables:**
- `src/mysti/engine/entity_extractor.py` — EntityExtractor
- `src/mysti/engine/graph_query.py` — GraphQuery
- Updated RAG pipeline with graph integration
- Entity-aware memory search

**Estimated effort:** 2-3 days

---

### Phase E: Intelligence Layer
**Model routing, proactive behavior, streaming, auto-memory extraction**

The Intelligence Layer makes MYSTI truly intelligent. It routes tasks to optimal models, proactively surfaces relevant information, streams responses in real-time, and automatically extracts facts from conversations.

**Key deliverables:**
- `src/mysti/engine/proactive.py` — ProactiveEngine
- `src/mysti/engine/auto_memory.py` — AutoMemoryExtractor
- Updated AgentCore with model routing
- Streaming API endpoint (SSE)
- Goal/project awareness

**Estimated effort:** 3-4 days

---

### Phase F: Polish & Production
**Wire everything together, optimize, full test suite**

Phase F wires all remaining systems (export, notifications, backup, voice, goals) into the AI Engine and optimizes performance. This makes MYSTI production-ready.

**Key deliverables:**
- Wired export to CLI/API
- Wired notifications to agent events
- Wired backup to scheduler
- Wired voice to REPL
- Wired goals/projects/learning to agent
- Performance optimization
- Full integration test suite
- Updated documentation

**Estimated effort:** 4-5 days

---

## Implementation Order

```
Phase A (Agent Core)
    ↓
Phase B (Memory-Augmented Generation)
    ↓
Phase C (Tool Integration)
    ↓
Phase D (Knowledge Integration)
    ↓
Phase E (Intelligence Layer)
    ↓
Phase F (Polish & Production)
```

**Total estimated effort:** 17-23 days

---

## Dependencies

### New Dependencies

| Dependency | Phase | Purpose |
|------------|-------|---------|
| `tiktoken` | A | Token counting for context window |
| `sse-starlette` | E | SSE streaming for API |
| `websockets` | E | WebSocket streaming |

### Existing Dependencies Used

| Dependency | Phases | Purpose |
|------------|--------|---------|
| `fastapi` | A, C, E | API framework |
| `uvicorn` | A, E | ASGI server |
| `pydantic` | All | Data validation |
| `cryptography` | All | Encryption |
| `httpx` | C, D | HTTP client |
| `beautifulsoup4` | C | HTML parsing |
| `numpy` | B, D | Similarity calculations |
| `apscheduler` | E, F | Task scheduling |

---

## File Structure

```
src/mysti/engine/
├── __init__.py
├── core.py              # AgentCore — central orchestration
├── state.py             # AgentState, AgentStep, AgentResult
├── prompt.py            # DynamicPromptBuilder
├── loop.py              # Main agent loop
├── rag.py               # RAGPipeline — memory retrieval + injection
├── memory_ranker.py     # MemoryRanker — score and filter memories
├── memory_injector.py   # MemoryInjector — add memories to context
├── tool_executor.py     # ToolExecutor — execute tools during conversation
├── function_calling.py  # FunctionCalling — LLM function calling support
├── entity_extractor.py  # EntityExtractor — extract entities from text
├── graph_query.py       # GraphQuery — query knowledge graph
├── proactive.py         # ProactiveEngine — surface relevant information
├── auto_memory.py       # AutoMemoryExtractor — extract facts from chat
└── streaming.py         # StreamingManager — SSE/WebSocket streaming
```

---

## Testing Strategy

### Unit Tests
- Test each engine component in isolation
- Mock external dependencies (LLM, storage, tools)
- Test error handling and fallbacks

### Integration Tests
- Test complete agent loops
- Test tool calling end-to-end
- Test memory retrieval and injection
- Test knowledge graph integration

### End-to-End Tests
- Test full user conversations
- Test multi-turn memory updates
- Test proactive suggestions
- Test streaming responses

### Performance Tests
- Measure response latency
- Measure memory usage
- Measure tool execution time
- Benchmark against baseline

---

## Success Criteria

The AI Engine is complete when:

1. **Agent Loop Works** — User can have conversations with tool calling
2. **Memory is Used** — Relevant memories are retrieved and injected into responses
3. **Tools are Callable** — AI can use filesystem, browser, terminal, etc.
4. **Knowledge is Integrated** — Entities are extracted and used for context
5. **Routing Works** — Tasks are routed to optimal models
6. **Proactive Behavior** — AI surfaces relevant information without being asked
7. **Streaming Works** — Responses stream in real-time
8. **Auto-Memory Works** — Facts are extracted from conversations
9. **Cross-Platform** — Works on Windows and Linux
10. **Production Ready** — Full test suite, documentation, deployment guide

---

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM context window exceeded | Responses fail | Smart truncation, memory ranking |
| Tool execution timeout | Agent hangs | Timeout limits, fallback to no-tool mode |
| Knowledge graph grows too large | Performance degrades | Periodic pruning, relevance filtering |
| Model routing fails | Wrong model used | Fallback chain, manual override |
| Streaming connection drops | User loses response | Reconnection, response caching |
| Cross-platform issues | Feature doesn't work | Platform-specific testing |

---

*The AI Engine transforms MYSTI from a memory system into an intelligent personal AI.*
