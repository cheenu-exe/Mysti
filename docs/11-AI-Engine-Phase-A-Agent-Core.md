# AI Engine Phase A: Agent Core

## Phase Overview

Phase A builds the central orchestration loop — the "brain" of MYSTI. Currently, the REPL simply passes text to the LLM and returns the response. The Agent Core transforms this into an intelligent system that understands intent, decides what to do, executes actions, and generates context-aware responses.

The Agent Core implements the **Understand → Decide → Act → Respond** cycle, making MYSTI capable of autonomous decision-making within its permission boundaries.

---

## Goals and Success Criteria

### Primary Goals

1. **Create the AgentCore class** — Central orchestration that manages the conversation loop
2. **Implement the agent loop** — Understand → Decide → Act → Respond cycle
3. **Add dynamic prompt construction** — Build prompts based on context, not hardcoded
4. **Wire into CLI and API** — Replace simple REPL with agent-driven conversation
5. **Add loop protection** — Prevent infinite loops and excessive iterations

### Success Criteria

You know Phase A is complete when:

- User can have a conversation through the agent loop
- Agent understands user intent and decides what to do
- Agent generates context-aware responses
- CLI REPL uses the agent loop
- API `/agent/chat` endpoint works
- Loop protection prevents infinite iterations
- All existing tests still pass

---

## Architecture

### Current State

```
CLI REPL                    API
    │                        │
    ↓                        ↓
ChatRepl.run()          FastAPI endpoint
    │                        │
    ↓                        ↓
LLM.complete()          LLM.complete()
    │                        │
    ↓                        ↓
Response                Response
```

**Problem:** No decision-making. The AI just passes text to the LLM and returns the response.

### Phase A Target State

```
CLI REPL                    API
    │                        │
    ↓                        ↓
AgentCore.chat()        AgentCore.chat()
    │                        │
    ↓                        │
┌───────────────────────────┐│
│        Agent Loop         ││
│  ┌──────────────────┐    ││
│  │ 1. Understand     │    ││
│  │    Parse intent   │    ││
│  └─────────┬────────┘    ││
│            ↓             ││
│  ┌──────────────────┐    ││
│  │ 2. Decide         │    ││
│  │    What to do?    │    ││
│  └─────────┬────────┘    ││
│            ↓             ││
│  ┌──────────────────┐    ││
│  │ 3. Act            │    ││
│  │    Execute action │    ││
│  └─────────┬────────┘    ││
│            ↓             ││
│  ┌──────────────────┐    ││
│  │ 4. Respond        │    ││
│  │    Generate reply │    ││
│  └──────────────────┘    ││
└───────────────────────────┘│
    │                        │
    ↓                        ↓
Response                Response
```

### Agent Loop Flow

```
User Input
    │
    ↓
┌─────────────────────────────────────────────┐
│              Agent Loop                      │
│                                              │
│  ┌────────────────────────────────────────┐ │
│  │ Step 1: Understand                      │ │
│  │ - Parse user message                    │ │
│  │ - Extract intent                        │ │
│  │ - Identify entities                     │ │
│  │ - Determine context needed              │ │
│  └───────────────────┬────────────────────┘ │
│                      ↓                       │
│  ┌────────────────────────────────────────┐ │
│  │ Step 2: Decide                          │ │
│  │ - What tools to call?                   │ │
│  │ - What memories to retrieve?            │ │
│  │ - What context to build?                │ │
│  │ - What model to use?                    │ │
│  └───────────────────┬────────────────────┘ │
│                      ↓                       │
│  ┌────────────────────────────────────────┐ │
│  │ Step 3: Act                             │ │
│  │ - Execute tool calls                    │ │
│  │ - Retrieve memories                     │ │
│  │ - Query knowledge graph                 │ │
│  │ - Build context                         │ │
│  └───────────────────┬────────────────────┘ │
│                      ↓                       │
│  ┌────────────────────────────────────────┐ │
│  │ Step 4: Respond                         │ │
│  │ - Generate response with context        │ │
│  │ - Post-process output                   │ │
│  │ - Update conversation state             │ │
│  │ - Check for loop termination            │ │
│  └────────────────────────────────────────┘ │
│                      │                       │
│                      ↓                       │
│              Continue or Exit?               │
│              (max iterations)                │
└─────────────────────────────────────────────┘
    │
    ↓
Final Response
```

---

## Data Models

### AgentState

Tracks the current state of an agent conversation.

```python
@dataclass
class AgentState:
    session_id: str
    messages: list[MessageRecord]
    context: dict[str, Any]
    tools_called: list[ToolExecution]
    memories_used: list[str]
    current_step: int
    max_steps: int
    started_at: datetime
    last_activity: datetime
```

**Fields:**

- `session_id` — Unique identifier for this conversation
- `messages` — Full conversation history
- `context` — Dynamic context (memories, graph data, etc.)
- `tools_called` — Tools executed in this conversation
- `memories_used` — Memory IDs retrieved during conversation
- `current_step` — Current iteration in the agent loop
- `max_steps` — Maximum iterations before forced exit (default: 10)
- `started_at` — When the conversation started
- `last_activity` — Last user/agent message

### AgentAction

Represents what the agent decided to do.

```python
@dataclass
class AgentAction:
    action_type: str  # "respond", "tool_call", "memory_search", "graph_query"
    tool_name: str | None
    tool_args: dict[str, Any] | None
    memory_query: str | None
    graph_query: str | None
    reasoning: str
```

**Fields:**

- `action_type` — What kind of action to take
- `tool_name` — Name of tool to call (if action_type is "tool_call")
- `tool_args` — Arguments for the tool
- `memory_query` — Query for memory search
- `graph_query` — Query for knowledge graph
- `reasoning` — Why this action was chosen

### AgentStep

One step in the agent loop.

```python
@dataclass
class AgentStep:
    step_number: int
    input_text: str
    action: AgentAction
    output_text: str | None
    tool_results: list[ToolResult]
    memories_retrieved: list[str]
    duration_ms: float
    tokens_used: int
```

**Fields:**

- `step_number` — Sequential step number
- `input_text` — What was input to this step
- `action` — What the agent decided to do
- `output_text` — What was output (if respond action)
- `tool_results` — Results of any tool calls
- `memories_retrieved` — Memory IDs retrieved
- `duration_ms` — How long this step took
- `tokens_used` — Tokens consumed in this step

### AgentResult

Final result after all steps.

```python
@dataclass
class AgentResult:
    response: str
    steps: list[AgentStep]
    total_tokens: int
    total_duration_ms: float
    tools_used: list[str]
    memories_used: list[str]
    loop_terminated: str  # "normal", "max_steps", "error"
```

**Fields:**

- `response` — Final response to user
- `steps` — All steps taken
- `total_tokens` — Total tokens consumed
- `total_duration_ms` — Total time taken
- `tools_used` — Unique tools used
- `memories_used` — Unique memories used
- `loop_terminated` — Why the loop ended

---

## API Design

### POST /agent/chat

Send a message to the agent and get a response.

**Request:**

```json
{
  "session_id": "optional-session-id",
  "message": "What files are in my project?",
  "context": {
    "trust_level": "T2",
    "available_tools": ["filesystem", "terminal"]
  }
}
```

**Response:**

```json
{
  "session_id": "abc123",
  "response": "Your project has 3 directories: src, tests, docs...",
  "steps": [
    {
      "step_number": 1,
      "action": "tool_call",
      "tool_name": "filesystem",
      "tool_args": {"path": ".", "action": "list"},
      "duration_ms": 150
    },
    {
      "step_number": 2,
      "action": "respond",
      "output_text": "Your project has 3 directories...",
      "duration_ms": 2300
    }
  ],
  "total_tokens": 1250,
  "total_duration_ms": 2450,
  "tools_used": ["filesystem"],
  "memories_used": []
}
```

### POST /agent/chat/stream

Streaming version using SSE.

**Request:**

```json
{
  "session_id": "optional-session-id",
  "message": "Tell me about my cybersecurity project"
}
```

**Response (SSE):**

```
event: step
data: {"step_number": 1, "action": "memory_search", "query": "cybersecurity project"}

event: step
data: {"step_number": 2, "action": "respond", "output_text": "Your cybersecurity..."}

event: done
data: {"total_tokens": 890, "total_duration_ms": 3200}
```

### GET /agent/state/{session_id}

Get the current agent state.

**Response:**

```json
{
  "session_id": "abc123",
  "messages": [...],
  "context": {...},
  "tools_called": [...],
  "memories_used": [...],
  "current_step": 3,
  "max_steps": 10,
  "started_at": "2026-09-02T10:00:00Z",
  "last_activity": "2026-09-02T10:05:00Z"
}
```

### POST /agent/reset/{session_id}

Reset the agent state.

**Response:**

```json
{
  "status": "reset",
  "session_id": "abc123"
}
```

---

## Implementation Details

### Step 1: Create Engine Module Structure

Create the following files:

```
src/mysti/engine/
├── __init__.py
├── core.py
├── state.py
├── prompt.py
└── loop.py
```

### Step 2: Implement AgentState (state.py)

```python
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

@dataclass
class AgentState:
    session_id: str = field(default_factory=lambda: str(uuid4()))
    messages: list[dict] = field(default_factory=list)
    context: dict = field(default_factory=dict)
    tools_called: list[dict] = field(default_factory=list)
    memories_used: list[str] = field(default_factory=list)
    current_step: int = 0
    max_steps: int = 10
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_activity: datetime = field(default_factory=lambda: datetime.now(UTC))

    def add_message(self, role: str, content: str) -> None:
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now(UTC).isoformat()
        })
        self.last_activity = datetime.now(UTC)

    def increment_step(self) -> bool:
        self.current_step += 1
        return self.current_step < self.max_steps

    def to_context_messages(self) -> list[dict]:
        return [{"role": m["role"], "content": m["content"]} for m in self.messages]
```

### Step 3: Implement DynamicPromptBuilder (prompt.py)

```python
from __future__ import annotations
from typing import Any

class DynamicPromptBuilder:
    def __init__(self, base_system_prompt: str | None = None):
        self.base_prompt = base_system_prompt or self._default_system_prompt()
        self.sections: list[str] = []

    def _default_system_prompt(self) -> str:
        return (
            "You are MYSTI, a private, encrypted personal AI assistant. "
            "You help users with their tasks while maintaining strict privacy. "
            "You can use tools when appropriate and relevant memories will be "
            "provided in the context."
        )

    def add_memory_context(self, memories: list[dict]) -> None:
        if not memories:
            return
        section = "## Relevant Memories\n\n"
        for mem in memories:
            section += f"- [{mem.get('category', 'general')}] {mem.get('content', '')}\n"
        self.sections.append(section)

    def add_graph_context(self, entities: list[dict]) -> None:
        if not entities:
            return
        section = "## Related Knowledge\n\n"
        for ent in entities:
            section += f"- {ent.get('name', '')} ({ent.get('type', '')}): {ent.get('description', '')}\n"
        self.sections.append(section)

    def add_tool_results(self, results: list[dict]) -> None:
        if not results:
            return
        section = "## Tool Results\n\n"
        for res in results:
            section += f"- {res.get('tool', '')}: {res.get('output', '')}\n"
        self.sections.append(section)

    def build(self) -> str:
        prompt = self.base_prompt
        if self.sections:
            prompt += "\n\n" + "\n".join(self.sections)
        return prompt

    def reset(self) -> None:
        self.sections.clear()
```

### Step 4: Implement AgentCore (core.py)

```python
from __future__ import annotations
import asyncio
from typing import Any, Protocol

class LLMClient(Protocol):
    async def complete(self, messages: list[dict], **kwargs: Any) -> str: ...

class ToolGateway(Protocol):
    async def execute(self, tool_name: str, args: dict) -> Any: ...

class MemoryService(Protocol):
    async def search(self, query: str, category: str | None = None) -> list[Any]: ...

class AgentCore:
    def __init__(
        self,
        llm: LLMClient,
        tools: ToolGateway | None = None,
        memory: MemoryService | None = None,
        max_steps: int = 10,
    ):
        self.llm = llm
        self.tools = tools
        self.memory = memory
        self.max_steps = max_steps
        self._states: dict[str, AgentState] = {}

    def get_state(self, session_id: str) -> AgentState:
        if session_id not in self._states:
            self._states[session_id] = AgentState(
                session_id=session_id,
                max_steps=self.max_steps
            )
        return self._states[session_id]

    async def chat(self, session_id: str, message: str) -> AgentResult:
        state = self.get_state(session_id)
        state.add_message("user", message)

        steps = []
        total_tokens = 0
        total_duration = 0.0

        while state.increment_step():
            step_start = asyncio.get_event_loop().time()

            # Build context
            prompt_builder = DynamicPromptBuilder()
            system_prompt = prompt_builder.build()
            messages = [{"role": "system", "content": system_prompt}] + state.to_context_messages()

            # Call LLM
            response = await self.llm.complete(messages)
            total_tokens += len(response.split())  # Rough estimate

            step_duration = (asyncio.get_event_loop().time() - step_start) * 1000

            state.add_message("assistant", response)

            steps.append(AgentStep(
                step_number=state.current_step,
                input_text=message,
                action=AgentAction(action_type="respond", reasoning="LLM response"),
                output_text=response,
                tool_results=[],
                memories_retrieved=[],
                duration_ms=step_duration,
                tokens_used=len(response.split())
            ))

            # Exit loop (for now, simple single-step response)
            break

        return AgentResult(
            response=steps[-1].output_text if steps else "",
            steps=steps,
            total_tokens=total_tokens,
            total_duration_ms=sum(s.duration_ms for s in steps),
            tools_used=[],
            memories_used=state.memories_used,
            loop_terminated="normal"
        )

    def reset(self, session_id: str) -> None:
        if session_id in self._states:
            del self._states[session_id]
```

### Step 5: Update CLI REPL

Update `src/mysti/cli/repl.py` to use AgentCore:

```python
# In ChatRepl.run()
from mysti.engine.core import AgentCore

async def run(self):
    agent = AgentCore(llm=self.ctx.llm, memory=self.ctx.memory)

    while True:
        user_input = input("You: ")
        if user_input.lower() in ("exit", "quit"):
            break

        result = await agent.chat(self.session_id, user_input)
        print(f"MYSTI: {result.response}")
```

### Step 6: Update API

Update `src/mysti/api/app.py` to add agent endpoints:

```python
from fastapi import FastAPI
from pydantic import BaseModel

class AgentChatRequest(BaseModel):
    session_id: str | None = None
    message: str

class AgentChatResponse(BaseModel):
    session_id: str
    response: str
    steps: list[dict]
    total_tokens: int
    total_duration_ms: float

@app.post("/agent/chat", response_model=AgentChatResponse)
async def agent_chat(request: AgentChatRequest, ctx: AppContext = Depends(get_context)):
    agent = AgentCore(llm=ctx.llm, memory=ctx.memory)
    session_id = request.session_id or str(uuid4())
    result = await agent.chat(session_id, request.message)
    return AgentChatResponse(
        session_id=session_id,
        response=result.response,
        steps=[...],
        total_tokens=result.total_tokens,
        total_duration_ms=result.total_duration_ms
    )
```

### Step 7: Add Loop Protection

```python
class LoopProtectionError(MystiError):
    """Raised when agent loop exceeds max iterations."""
    pass

# In AgentCore.chat()
if state.current_step >= state.max_steps:
    raise LoopProtectionError(
        f"Agent loop exceeded {state.max_steps} iterations. "
        "Consider breaking the task into smaller steps."
    )
```

---

## Dependencies

### New Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| `tiktoken` | >=0.7 | Token counting for context window management |

### Existing Dependencies Used

| Dependency | Purpose |
|------------|---------|
| `pydantic` | Data validation for models |
| `fastapi` | API framework |
| `uvicorn` | ASGI server |
| `typer` | CLI framework |
| `rich` | CLI output formatting |

---

## Testing

### Unit Tests

**test_engine_state.py:**

```python
import pytest
from mysti.engine.state import AgentState

def test_agent_state_creation():
    state = AgentState(session_id="test-session")
    assert state.session_id == "test-session"
    assert state.current_step == 0
    assert state.messages == []

def test_agent_state_add_message():
    state = AgentState()
    state.add_message("user", "Hello")
    assert len(state.messages) == 1
    assert state.messages[0]["role"] == "user"
    assert state.messages[0]["content"] == "Hello"

def test_agent_state_increment_step():
    state = AgentState(max_steps=3)
    assert state.increment_step() is True
    assert state.current_step == 1
    assert state.increment_step() is True
    assert state.current_step == 2
    assert state.increment_step() is False
    assert state.current_step == 3

def test_agent_state_to_context_messages():
    state = AgentState()
    state.add_message("user", "Hello")
    state.add_message("assistant", "Hi there")
    messages = state.to_context_messages()
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
```

**test_engine_prompt.py:**

```python
import pytest
from mysti.engine.prompt import DynamicPromptBuilder

def test_prompt_builder_default():
    builder = DynamicPromptBuilder()
    prompt = builder.build()
    assert "MYSTI" in prompt
    assert "personal AI" in prompt

def test_prompt_builder_with_memory():
    builder = DynamicPromptBuilder()
    builder.add_memory_context([
        {"category": "projects", "content": "Working on MYSTI project"}
    ])
    prompt = builder.build()
    assert "Relevant Memories" in prompt
    assert "MYSTI project" in prompt

def test_prompt_builder_reset():
    builder = DynamicPromptBuilder()
    builder.add_memory_context([{"content": "test"}])
    builder.reset()
    prompt = builder.build()
    assert "Relevant Memories" not in prompt
```

**test_engine_core.py:**

```python
import pytest
from unittest.mock import AsyncMock
from mysti.engine.core import AgentCore, AgentResult

@pytest.mark.asyncio
async def test_agent_core_chat():
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = "Hello! How can I help you?"

    agent = AgentCore(llm=mock_llm)
    result = await agent.chat("session-1", "Hi")

    assert isinstance(result, AgentResult)
    assert result.response == "Hello! How can I help you?"
    assert len(result.steps) == 1

@pytest.mark.asyncio
async def test_agent_core_loop_protection():
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = "Response"

    agent = AgentCore(llm=mock_llm, max_steps=2)
    result = await agent.chat("session-1", "Test")

    assert result.loop_terminated == "normal"
    assert len(result.steps) <= 2

@pytest.mark.asyncio
async def test_agent_core_session_state():
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = "Response"

    agent = AgentCore(llm=mock_llm)
    await agent.chat("session-1", "Message 1")
    await agent.chat("session-1", "Message 2")

    state = agent.get_state("session-1")
    assert len(state.messages) == 4  # 2 user + 2 assistant
```

### Integration Tests

**test_agent_integration.py:**

```python
import pytest
from mysti.engine.core import AgentCore

@pytest.mark.asyncio
async def test_agent_full_conversation():
    # This would use a real LLM client in integration tests
    # For now, test with mock
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = "I can help you with that."

    agent = AgentCore(llm=mock_llm)
    result = await agent.chat("test", "What can you do?")

    assert result.response
    assert result.total_tokens > 0
    assert result.total_duration_ms > 0
```

---

## Edge Cases

### LLM Returns Empty Response

```python
response = await self.llm.complete(messages)
if not response or not response.strip():
    response = "I apologize, but I couldn't generate a response. Please try again."
```

### Context Window Exceeded

```python
# Check token count before calling LLM
token_count = len(tokenizer.encode(str(messages)))
if token_count > MAX_CONTEXT_TOKENS:
    # Truncate oldest messages
    messages = truncate_messages(messages, MAX_CONTEXT_TOKENS)
```

### Session Not Found

```python
def get_state(self, session_id: str) -> AgentState:
    if session_id not in self._states:
        # Create new state
        self._states[session_id] = AgentState(
            session_id=session_id,
            max_steps=self.max_steps
        )
    return self._states[session_id]
```

### Concurrent Access

```python
import asyncio

class AgentCore:
    def __init__(self, ...):
        self._locks: dict[str, asyncio.Lock] = {}

    async def chat(self, session_id: str, message: str) -> AgentResult:
        if session_id not in self._locks:
            self._locks[session_id] = asyncio.Lock()

        async with self._locks[session_id]:
            # Process message
            ...
```

### Memory Pressure

```python
# Limit stored states
MAX_SESSIONS = 100

def _cleanup_old_sessions(self):
    if len(self._states) > MAX_SESSIONS:
        # Remove oldest sessions
        sorted_sessions = sorted(
            self._states.items(),
            key=lambda x: x[1].last_activity
        )
        for session_id, _ in sorted_sessions[:MAX_SESSIONS // 2]:
            del self._states[session_id]
```

---

## Deliverables

When Phase A is complete, you will have:

1. **`src/mysti/engine/__init__.py`** — Module exports
2. **`src/mysti/engine/state.py`** — AgentState, AgentStep, AgentResult
3. **`src/mysti/engine/prompt.py`** — DynamicPromptBuilder
4. **`src/mysti/engine/core.py`** — AgentCore class
5. **`src/mysti/engine/loop.py`** — Main agent loop (extracted from core)
6. **Updated CLI REPL** — Uses AgentCore
7. **Updated API** — New `/agent/chat` endpoint
8. **Tests** — 10+ unit tests, 2+ integration tests

---

## What Comes Next

After Phase A, you will move to **Phase B: Memory-Augmented Generation**, which adds:
- RAG pipeline for memory retrieval
- Memory ranking and filtering
- Memory injection into context
- Memory feedback loop

Phase A's agent core provides the foundation for memory integration, with the agent loop ready to call the RAG pipeline during the Decide phase.

---

*Phase A creates the brain of MYSTI — the central orchestration that makes decisions and takes actions.*
