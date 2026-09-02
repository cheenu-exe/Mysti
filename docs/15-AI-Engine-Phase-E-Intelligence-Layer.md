# AI Engine Phase E: Intelligence Layer

## Phase Overview

Phase E adds intelligence behaviors that make MYSTI proactive — not just reactive. Currently, the AI only responds when asked. This phase adds model routing (select the best model per task), proactive behavior (surface relevant information), streaming responses (SSE), and auto-memory extraction (learn from conversations).

The Intelligence Layer transforms MYSTI from a question-answering system into an intelligent assistant that anticipates needs and adapts to context.

---

## Goals and Success Criteria

### Primary Goals

1. **Model routing** — Select best model per task (speed vs quality)
2. **Proactive behavior** — Surface relevant information before being asked
3. **Streaming responses** — SSE for real-time output
4. **Auto-memory extraction** — Learn from conversations automatically
5. **Task classification** — Understand what type of task is being performed

### Success Criteria

You know Phase E is complete when:

- Model routing selects appropriate models per task
- Proactive suggestions appear when relevant
- Responses stream in real-time
- Important information is automatically extracted
- Task classification works correctly
- All existing tests still pass

---

## Architecture

### Current State (Phase A+B+C+D)

```
User Input
    ↓
AgentCore.chat()
    ↓
┌─────────────────────────────┐
│  Entity Extraction          │
└──────────────┬──────────────┘
               ↓
┌─────────────────────────────┐
│  Knowledge Graph            │
└──────────────┬──────────────┘
               ↓
┌─────────────────────────────┐
│  RAG Pipeline               │
└──────────────┬──────────────┘
               ↓
┌─────────────────────────────┐
│  Tool Executor              │
└──────────────┬──────────────┘
               ↓
Response (complete)
```

**Problem:** No intelligence. No routing. No streaming. No proactive behavior.

### Phase E Target State

```
User Input
    ↓
┌─────────────────────────────┐
│  Task Classifier            │
│  - Classify intent          │
│  - Determine complexity     │
└──────────────┬──────────────┘
               ↓
┌─────────────────────────────┐
│  Model Router               │
│  - Select best model        │
│  - Balance speed/quality    │
└──────────────┬──────────────┘
               ↓
┌─────────────────────────────┐
│  Entity Extraction          │
└──────────────┬──────────────┘
               ↓
┌─────────────────────────────┐
│  Knowledge Graph            │
└──────────────┬──────────────┘
               ↓
┌─────────────────────────────┐
│  Proactive Engine           │
│  - Check for relevant info  │
│  - Surface suggestions      │
└──────────────┬──────────────┘
               ↓
┌─────────────────────────────┐
│  RAG Pipeline               │
└──────────────┬──────────────┘
               ↓
┌─────────────────────────────┐
│  Tool Executor              │
└──────────────┬──────────────┘
               ↓
┌─────────────────────────────┐
│  Auto-Memory Extraction     │
│  - Extract important info   │
│  - Store for future use     │
└──────────────┬──────────────┘
               ↓
┌─────────────────────────────┐
│  Streaming Response         │
│  - SSE for real-time        │
│  - Progressive output       │
└─────────────────────────────┘
```

### Intelligence Flow

```
User: "How is my MYSTI project progressing?"
    │
    ↓
┌─────────────────────────────────────────────┐
│  Intelligence Layer                          │
│                                              │
│  ┌────────────────────────────────────────┐ │
│  │ Step 1: Task Classification             │ │
│  │ - Intent: question_about_project        │ │
│  │ - Complexity: medium                    │ │
│  │ - Needs: factual, context               │ │
│  └───────────────────┬────────────────────┘ │
│                      ↓                       │
│  ┌────────────────────────────────────────┐ │
│  │ Step 2: Model Routing                   │ │
│  │ - Task type: factual question           │ │
│  │ - Best model: fast-model (speed)        │ │
│  │ - Reason: Quick factual lookup          │ │
│  └───────────────────┬────────────────────┘ │
│                      ↓                       │
│  ┌────────────────────────────────────────┐ │
│  │ Step 3: Proactive Check                 │ │
│  │ - Related: "MYSTI Phase D started"      │ │
│  │ - Suggest: "Want to see Phase D docs?"  │ │
│  └───────────────────┬────────────────────┘ │
│                      ↓                       │
│  ┌────────────────────────────────────────┐ │
│  │ Step 4: Generate Response               │ │
│  │ - Use fast-model                        │ │
│  │ - Include proactive suggestion          │ │
│  │ - Stream response                       │ │
│  └───────────────────┬────────────────────┘ │
│                      ↓                       │
│  ┌────────────────────────────────────────┐ │
│  │ Step 5: Auto-Extract                    │ │
│  │ - "MYSTI project progress" is important │ │
│  │ - Store as memory for future reference  │ │
│  └────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

---

## Data Models

### TaskClassification

Result of intent classification.

```python
@dataclass
class TaskClassification:
    intent: str  # "question", "command", "discussion", "research"
    complexity: str  # "simple", "medium", "complex"
    domain: str  # "general", "code", "research", "memory"
    confidence: float
    needs_tools: bool
    needs_memory: bool
    needs_knowledge: bool
```

### ModelRouting

Model selection result.

```python
@dataclass
class ModelRouting:
    model_id: str
    reason: str
    estimated_latency_ms: int
    estimated_cost: float
    quality_score: float
```

### ProactiveSuggestion

Suggestion for proactive behavior.

```python
@dataclass
class ProactiveSuggestion:
    suggestion_type: str  # "memory", "knowledge", "action", "related"
    content: str
    relevance_score: float
    action_url: str | None
    metadata: dict[str, Any]
```

### StreamingChunk

Chunk for streaming response.

```python
@dataclass
class StreamingChunk:
    content: str
    chunk_type: str  # "text", "tool_call", "metadata", "done"
    metadata: dict[str, Any]
    timestamp: str
```

### AutoMemory

Auto-extracted memory.

```python
@dataclass
class AutoMemory:
    content: str
    memory_type: str  # "fact", "preference", "project", "person"
    importance: float
    context: str
    source_message: str
```

---

## API Design

### POST /engine/classify

Classify a task.

**Request:**

```json
{
  "message": "How is my MYSTI project progressing?"
}
```

**Response:**

```json
{
  "intent": "question",
  "complexity": "medium",
  "domain": "general",
  "confidence": 0.9,
  "needs_tools": false,
  "needs_memory": true,
  "needs_knowledge": true
}
```

### POST /engine/route

Select best model for task.

**Request:**

```json
{
  "task_classification": {
    "intent": "question",
    "complexity": "medium",
    "domain": "general"
  }
}
```

**Response:**

```json
{
  "model_id": "gpt-4o-mini",
  "reason": "Factual question, medium complexity, speed preferred",
  "estimated_latency_ms": 500,
  "estimated_cost": 0.0001,
  "quality_score": 0.85
}
```

### GET /engine/proactive/{session_id}

Get proactive suggestions.

**Query Parameters:**

- `limit` — Maximum suggestions (default: 5)
- `min_relevance` — Minimum relevance score (default: 0.5)

**Response:**

```json
{
  "suggestions": [
    {
      "suggestion_type": "knowledge",
      "content": "MYSTI Phase D documentation is available",
      "relevance_score": 0.8,
      "action_url": "/knowledge/entity/ent-001",
      "metadata": {"project": "MYSTI", "phase": "D"}
    }
  ]
}
```

### POST /engine/stream

Stream response with SSE.

**Request:**

```json
{
  "session_id": "sess-123",
  "message": "Tell me about MYSTI"
}
```

**SSE Response:**

```
data: {"content": "MYSTI", "chunk_type": "text", "metadata": {}}
data: {"content": " is", "chunk_type": "text", "metadata": {}}
data: {"content": " a", "chunk_type": "text", "metadata": {}}
data: {"content": " personal", "chunk_type": "text", "metadata": {}}
data: {"content": " AI", "chunk_type": "text", "metadata": {}}
data: {"content": " operating", "chunk_type": "text", "metadata": {}}
data: {"content": " layer", "chunk_type": "text", "metadata": {}}
data: {"content": "", "chunk_type": "done", "metadata": {"total_tokens": 150}}
```

---

## Implementation Details

### Step 1: Create Intelligence Module

Create the following files:

```
src/mysti/engine/
├── task_classifier.py
├── model_router.py
├── proactive_engine.py
└── auto_memory.py
```

### Step 2: Implement TaskClassifier (task_classifier.py)

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Protocol

class LLMClient(Protocol):
    async def complete(self, messages: list[dict], **kwargs: Any) -> str: ...

@dataclass
class TaskClassification:
    intent: str
    complexity: str
    domain: str
    confidence: float
    needs_tools: bool
    needs_memory: bool
    needs_knowledge: bool

class TaskClassifier:
    def __init__(self, llm: LLMClient):
        self.llm = llm
        self._classification_prompt = """Classify the following user message into:
- intent: question, command, discussion, research
- complexity: simple, medium, complex
- domain: general, code, research, memory
- needs_tools: whether the task likely needs tool usage
- needs_memory: whether the task benefits from memory context
- needs_knowledge: whether the task benefits from knowledge graph

User message: {message}

Return a JSON object with these fields. Be precise and consider the full context."""

    async def classify(self, message: str) -> TaskClassification:
        prompt = self._classification_prompt.format(message=message)
        response = await self.llm.complete([
            {"role": "user", "content": prompt}
        ])

        try:
            import json
            data = json.loads(response)

            return TaskClassification(
                intent=data.get("intent", "discussion"),
                complexity=data.get("complexity", "medium"),
                domain=data.get("domain", "general"),
                confidence=float(data.get("confidence", 0.8)),
                needs_tools=bool(data.get("needs_tools", False)),
                needs_memory=bool(data.get("needs_memory", True)),
                needs_knowledge=bool(data.get("needs_knowledge", False)),
            )

        except (json.JSONDecodeError, KeyError):
            # Fallback classification
            return TaskClassification(
                intent="discussion",
                complexity="medium",
                domain="general",
                confidence=0.5,
                needs_tools=False,
                needs_memory=True,
                needs_knowledge=False,
            )

    def _simple_classify(self, message: str) -> TaskClassification:
        # Simple rule-based classification as fallback
        message_lower = message.lower()

        # Detect intent
        if message_lower.startswith(("how", "what", "why", "when", "where", "who")):
            intent = "question"
        elif message_lower.startswith(("do", "run", "execute", "create", "delete")):
            intent = "command"
        elif "?" in message:
            intent = "question"
        else:
            intent = "discussion"

        # Detect complexity
        if len(message.split()) < 10:
            complexity = "simple"
        elif len(message.split()) < 30:
            complexity = "medium"
        else:
            complexity = "complex"

        # Detect domain
        if any(word in message_lower for word in ["code", "function", "class", "api"]):
            domain = "code"
        elif any(word in message_lower for word in ["memory", "remember", "recall"]):
            domain = "memory"
        elif any(word in message_lower for word in ["research", "find", "search"]):
            domain = "research"
        else:
            domain = "general"

        return TaskClassification(
            intent=intent,
            complexity=complexity,
            domain=domain,
            confidence=0.7,
            needs_tools=intent == "command",
            needs_memory=True,
            needs_knowledge=domain == "research",
        )
```

### Step 3: Implement ModelRouter (model_router.py)

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Protocol
from .task_classifier import TaskClassification

class LLMClient(Protocol):
    async def complete(self, messages: list[dict], **kwargs: Any) -> str: ...
    async def stream(self, messages: list[dict], **kwargs: Any) -> Any: ...

@dataclass
class ModelConfig:
    model_id: str
    name: str
    max_tokens: int
    cost_per_1k_tokens: float
    average_latency_ms: int
    quality_score: float
    capabilities: list[str]

@dataclass
class ModelRouting:
    model_id: str
    reason: str
    estimated_latency_ms: int
    estimated_cost: float
    quality_score: float

class ModelRouter:
    def __init__(self):
        self.models = [
            ModelConfig(
                model_id="gpt-4o-mini",
                name="GPT-4o Mini",
                max_tokens=4096,
                cost_per_1k_tokens=0.00015,
                average_latency_ms=300,
                quality_score=0.85,
                capabilities=["general", "code", "research"],
            ),
            ModelConfig(
                model_id="gpt-4o",
                name="GPT-4o",
                max_tokens=4096,
                cost_per_1k_tokens=0.005,
                average_latency_ms=800,
                quality_score=0.95,
                capabilities=["general", "code", "research", "complex"],
            ),
            ModelConfig(
                model_id="gpt-3.5-turbo",
                name="GPT-3.5 Turbo",
                max_tokens=4096,
                cost_per_1k_tokens=0.0001,
                average_latency_ms=200,
                quality_score=0.75,
                capabilities=["general", "simple"],
            ),
        ]

    def route(self, classification: TaskClassification) -> ModelRouting:
        # Select model based on classification
        if classification.complexity == "complex" or classification.domain == "code":
            # Use best model for complex tasks
            model = self.models[1]  # GPT-4o
            reason = "Complex task or code domain, quality preferred"
        elif classification.complexity == "simple" and classification.intent == "question":
            # Use fast model for simple questions
            model = self.models[2]  # GPT-3.5
            reason = "Simple question, speed preferred"
        else:
            # Default to balanced model
            model = self.models[0]  # GPT-4o Mini
            reason = "Balanced speed and quality"

        return ModelRouting(
            model_id=model.model_id,
            reason=reason,
            estimated_latency_ms=model.average_latency_ms,
            estimated_cost=model.cost_per_1k_tokens * 0.001,  # Estimate
            quality_score=model.quality_score,
        )

    def get_model_config(self, model_id: str) -> ModelConfig | None:
        for model in self.models:
            if model.model_id == model_id:
                return model
        return None
```

### Step 4: Implement ProactiveEngine (proactive_engine.py)

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Protocol

class MemoryService(Protocol):
    async def search(self, query: str, limit: int = 5) -> list[Any]: ...

class KnowledgeGraph(Protocol):
    async def search_entities(self, query: str) -> list[Any]: ...

@dataclass
class ProactiveSuggestion:
    suggestion_type: str
    content: str
    relevance_score: float
    action_url: str | None
    metadata: dict[str, Any]

class ProactiveEngine:
    def __init__(
        self,
        memory: MemoryService | None = None,
        knowledge_graph: KnowledgeGraph | None = None,
    ):
        self.memory = memory
        self.knowledge_graph = knowledge_graph

    async def get_suggestions(
        self,
        session_id: str,
        current_message: str,
        conversation_history: list[dict[str, str]],
        limit: int = 5,
        min_relevance: float = 0.5,
    ) -> list[ProactiveSuggestion]:
        suggestions = []

        # Check for relevant memories
        if self.memory:
            memory_suggestions = await self._get_memory_suggestions(
                current_message, conversation_history
            )
            suggestions.extend(memory_suggestions)

        # Check for relevant knowledge
        if self.knowledge_graph:
            knowledge_suggestions = await self._get_knowledge_suggestions(
                current_message
            )
            suggestions.extend(knowledge_suggestions)

        # Check for related actions
        action_suggestions = await self._get_action_suggestions(
            current_message, conversation_history
        )
        suggestions.extend(action_suggestions)

        # Sort by relevance and limit
        suggestions.sort(key=lambda s: s.relevance_score, reverse=True)
        suggestions = [s for s in suggestions if s.relevance_score >= min_relevance]

        return suggestions[:limit]

    async def _get_memory_suggestions(
        self,
        current_message: str,
        conversation_history: list[dict[str, str]],
    ) -> list[ProactiveSuggestion]:
        suggestions = []

        # Search for relevant memories
        memories = await self.memory.search(current_message, limit=3)

        for memory in memories:
            if memory.relevance_score > 0.7:
                suggestions.append(ProactiveSuggestion(
                    suggestion_type="memory",
                    content=f"Relevant memory: {memory.content[:100]}...",
                    relevance_score=memory.relevance_score,
                    action_url=f"/memory/{memory.id}",
                    metadata={"memory_id": memory.id},
                ))

        return suggestions

    async def _get_knowledge_suggestions(
        self,
        current_message: str,
    ) -> list[ProactiveSuggestion]:
        suggestions = []

        # Search for relevant entities
        entities = await self.knowledge_graph.search_entities(current_message)

        for entity in entities[:2]:
            suggestions.append(ProactiveSuggestion(
                suggestion_type="knowledge",
                content=f"Related entity: {entity.name} ({entity.entity_type})",
                relevance_score=0.7,
                action_url=f"/knowledge/entity/{entity.id}",
                metadata={"entity_id": entity.id, "entity_type": entity.entity_type},
            ))

        return suggestions

    async def _get_action_suggestions(
        self,
        current_message: str,
        conversation_history: list[dict[str, str]],
    ) -> list[ProactiveSuggestion]:
        suggestions = []

        # Detect potential actions based on conversation
        message_lower = current_message.lower()

        if "remember" in message_lower or "forget" in message_lower:
            suggestions.append(ProactiveSuggestion(
                suggestion_type="action",
                content="Manage your memories",
                relevance_score=0.8,
                action_url="/memory",
                metadata={"action": "manage_memory"},
            ))

        if "research" in message_lower or "find" in message_lower:
            suggestions.append(ProactiveSuggestion(
                suggestion_type="action",
                content="Start a research session",
                relevance_score=0.7,
                action_url="/research",
                metadata={"action": "start_research"},
            ))

        if "project" in message_lower:
            suggestions.append(ProactiveSuggestion(
                suggestion_type="action",
                content="View project dashboard",
                relevance_score=0.6,
                action_url="/dashboard",
                metadata={"action": "view_dashboard"},
            ))

        return suggestions
```

### Step 5: Implement AutoMemory (auto_memory.py)

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Protocol

class LLMClient(Protocol):
    async def complete(self, messages: list[dict], **kwargs: Any) -> str: ...

class MemoryService(Protocol):
    async def add(self, content: str, memory_type: str, importance: float, metadata: dict) -> Any: ...

@dataclass
class AutoMemory:
    content: str
    memory_type: str
    importance: float
    context: str
    source_message: str

class AutoMemoryExtractor:
    def __init__(
        self,
        llm: LLMClient,
        memory: MemoryService | None = None,
        enabled: bool = True,
        min_importance: float = 0.6,
    ):
        self.llm = llm
        self.memory = memory
        self.enabled = enabled
        self.min_importance = min_importance
        self._extraction_prompt = """Extract important information from this conversation that should be remembered for future reference.

User message: {message}
Assistant response: {response}

Return a JSON object with:
- memories: list of {{content, memory_type, importance, context}}
  - memory_type: "fact", "preference", "project", "person"
  - importance: 0.0-1.0 (only extract if >= {min_importance})
  - context: Why this is important

Only extract genuinely important information. Don't extract trivial details."""

    async def extract_and_store(
        self,
        user_message: str,
        assistant_response: str,
        session_id: str,
    ) -> list[AutoMemory]:
        if not self.enabled or not self.memory:
            return []

        prompt = self._extraction_prompt.format(
            message=user_message,
            response=assistant_response,
            min_importance=self.min_importance,
        )

        response = await self.llm.complete([
            {"role": "user", "content": prompt}
        ])

        try:
            import json
            data = json.loads(response)
            memories = []

            for item in data.get("memories", []):
                importance = float(item.get("importance", 0.5))

                if importance < self.min_importance:
                    continue

                auto_memory = AutoMemory(
                    content=item.get("content", ""),
                    memory_type=item.get("memory_type", "fact"),
                    importance=importance,
                    context=item.get("context", ""),
                    source_message=user_message[:200],
                )

                # Store in memory service
                await self.memory.add(
                    content=auto_memory.content,
                    memory_type=auto_memory.memory_type,
                    importance=auto_memory.importance,
                    metadata={
                        "context": auto_memory.context,
                        "source": "auto_extract",
                        "session_id": session_id,
                    },
                )

                memories.append(auto_memory)

            return memories

        except (json.JSONDecodeError, KeyError):
            return []

    async def extract_from_conversation(
        self,
        messages: list[dict[str, str]],
        session_id: str,
    ) -> list[AutoMemory]:
        if len(messages) < 2:
            return []

        all_memories = []

        # Process pairs of messages
        for i in range(len(messages) - 1):
            if messages[i]["role"] == "user" and messages[i + 1]["role"] == "assistant":
                memories = await self.extract_and_store(
                    messages[i]["content"],
                    messages[i + 1]["content"],
                    session_id,
                )
                all_memories.extend(memories)

        return all_memories
```

### Step 6: Wire into AgentCore

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

        # Initialize intelligence components
        self.task_classifier = TaskClassifier(llm=llm)
        self.model_router = ModelRouter()
        self.proactive_engine = ProactiveEngine(memory=memory, knowledge_graph=knowledge_graph)
        self.auto_memory = AutoMemoryExtractor(llm=llm, memory=memory)
        self.streaming = streaming

    async def chat(self, session_id: str, message: str) -> AgentResult:
        state = self.get_state(session_id)
        state.add_message("user", message)

        steps = []
        total_tokens = 0
        tools_used = []

        # Step 1: Classify task
        classification = await self.task_classifier.classify(message)
        logger.info(
            "Task classified",
            intent=classification.intent,
            complexity=classification.complexity,
        )

        # Step 2: Route to model
        routing = self.model_router.route(classification)
        logger.info(
            "Model routed",
            model_id=routing.model_id,
            reason=routing.reason,
        )

        # Step 3: Get proactive suggestions
        proactive_suggestions = await self.proactive_engine.get_suggestions(
            session_id=session_id,
            current_message=message,
            conversation_history=state.to_context_messages(),
        )

        # Step 4: Extract entities from user message
        if self.entity_extractor:
            await self.entity_extractor.extract_and_store(message)

        # Step 5: Get knowledge graph context
        graph_context_str = ""
        if self.graph_query:
            graph_context = await self.graph_query.query_for_context(message)
            graph_context_str = await self.graph_query.format_context_for_llm(graph_context)

        # Step 6: Retrieve relevant memories
        memories_used = []
        if self.rag and classification.needs_memory:
            enhanced_messages, memories = await self.rag.enhance_context(
                state.to_context_messages(),
                message
            )
            memories_used = [m.memory_id for m in memories]
            state.memories_used.extend(memories_used)
        else:
            enhanced_messages = state.to_context_messages()

        # Step 7: Build system prompt with all context
        prompt_builder = DynamicPromptBuilder()

        # Add proactive suggestions
        if proactive_suggestions:
            suggestions_text = "\n".join([
                f"- {s.content}" for s in proactive_suggestions[:3]
            ])
            prompt_builder.add_section(f"## Proactive Suggestions\n{suggestions_text}")

        # Add knowledge graph context
        if graph_context_str:
            prompt_builder.add_section(graph_context_str)

        # Add tool definitions
        if self.tool_executor:
            tool_definitions = self.tool_executor.format_tools_for_prompt()
            if tool_definitions:
                prompt_builder.add_section(tool_definitions)

        system_prompt = prompt_builder.build()
        messages = [{"role": "system", "content": system_prompt}] + enhanced_messages

        # Step 8: Execute agent loop with routing
        # Use routed model
        current_model = self.model_router.get_model_config(routing.model_id)

        # ... rest of the agent loop ...

        # Step 9: Auto-extract memories
        if self.auto_memory:
            await self.auto_memory.extract_and_store(
                user_message=message,
                assistant_response=state.get_assistant_messages()[-1].content if state.get_assistant_messages() else "",
                session_id=session_id,
            )

        # Step 10: Return result with proactive suggestions
        return AgentResult(
            session_id=session_id,
            response=state.get_assistant_messages()[-1].content if state.get_assistant_messages() else "",
            messages=state.messages,
            steps=steps,
            total_tokens=total_tokens,
            tools_used=tools_used,
            memories_used=memories_used,
            metadata={
                "task_classification": classification,
                "model_routing": routing,
                "proactive_suggestions": proactive_suggestions,
            },
        )

    async def chat_stream(self, session_id: str, message: str):
        """Stream response with SSE."""
        state = self.get_state(session_id)
        state.add_message("user", message)

        # Classify and route
        classification = await self.task_classifier.classify(message)
        routing = self.model_router.route(classification)

        # Get proactive suggestions
        proactive_suggestions = await self.proactive_engine.get_suggestions(
            session_id=session_id,
            current_message=message,
            conversation_history=state.to_context_messages(),
        )

        # Yield proactive suggestions first
        for suggestion in proactive_suggestions:
            yield StreamingChunk(
                content="",
                chunk_type="metadata",
                metadata={"proactive_suggestion": suggestion},
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        # Stream response
        # ... streaming implementation ...

        yield StreamingChunk(
            content="",
            chunk_type="done",
            metadata={"total_tokens": total_tokens},
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
```

---

## Dependencies

### New Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| None | - | Uses existing LLM, Memory, Knowledge components |

### Existing Dependencies Used

| Dependency | Purpose |
|------------|---------|
| `core/llm.py` | LLM for classification and extraction |
| `memory/service.py` | Memory search and storage |
| `integration/knowledge_graph.py` | Entity search |
| `engine/core.py` | Agent orchestration |

---

## Testing

### Unit Tests

**test_task_classifier.py:**

```python
import pytest
from unittest.mock import AsyncMock
from mysti.engine.task_classifier import TaskClassifier, TaskClassification

@pytest.mark.asyncio
async def test_classify_question():
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = '''
    {
        "intent": "question",
        "complexity": "medium",
        "domain": "general",
        "confidence": 0.9,
        "needs_tools": false,
        "needs_memory": true,
        "needs_knowledge": false
    }
    '''

    classifier = TaskClassifier(llm=mock_llm)
    result = await classifier.classify("How is my project?")

    assert result.intent == "question"
    assert result.complexity == "medium"

@pytest.mark.asyncio
async def test_classify_command():
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = '''
    {
        "intent": "command",
        "complexity": "simple",
        "domain": "general",
        "confidence": 0.85,
        "needs_tools": true,
        "needs_memory": false,
        "needs_knowledge": false
    }
    '''

    classifier = TaskClassifier(llm=mock_llm)
    result = await classifier.classify("Run the backup")

    assert result.intent == "command"
    assert result.needs_tools == True

def test_simple_classify():
    classifier = TaskClassifier(llm=None)
    result = classifier._simple_classify("What is 2+2?")

    assert result.intent == "question"
    assert result.complexity == "simple"
```

**test_model_router.py:**

```python
import pytest
from mysti.engine.model_router import ModelRouter, TaskClassification

def test_route_simple_question():
    router = ModelRouter()
    classification = TaskClassification(
        intent="question",
        complexity="simple",
        domain="general",
        confidence=0.9,
        needs_tools=False,
        needs_memory=True,
        needs_knowledge=False,
    )

    routing = router.route(classification)

    assert routing.model_id == "gpt-3.5-turbo"
    assert "speed" in routing.reason.lower()

def test_route_complex_task():
    router = ModelRouter()
    classification = TaskClassification(
        intent="command",
        complexity="complex",
        domain="code",
        confidence=0.8,
        needs_tools=True,
        needs_memory=False,
        needs_knowledge=False,
    )

    routing = router.route(classification)

    assert routing.model_id == "gpt-4o"
    assert "quality" in routing.reason.lower()
```

**test_proactive_engine.py:**

```python
import pytest
from unittest.mock import AsyncMock
from mysti.engine.proactive_engine import ProactiveEngine

@pytest.mark.asyncio
async def test_get_suggestions():
    mock_memory = AsyncMock()
    mock_memory.search.return_value = []

    mock_graph = AsyncMock()
    mock_graph.search_entities.return_value = []

    engine = ProactiveEngine(memory=mock_memory, knowledge_graph=mock_graph)
    suggestions = await engine.get_suggestions(
        session_id="test",
        current_message="Tell me about MYSTI",
        conversation_history=[],
    )

    assert isinstance(suggestions, list)
```

**test_auto_memory.py:**

```python
import pytest
from unittest.mock import AsyncMock
from mysti.engine.auto_memory import AutoMemoryExtractor

@pytest.mark.asyncio
async def test_extract_and_store():
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = '''
    {
        "memories": [
            {
                "content": "User is working on MYSTI project",
                "memory_type": "project",
                "importance": 0.8,
                "context": "Important for future context"
            }
        ]
    }
    '''

    mock_memory = AsyncMock()

    extractor = AutoMemoryExtractor(llm=mock_llm, memory=mock_memory)
    memories = await extractor.extract_and_store(
        user_message="I'm working on MYSTI",
        assistant_response="Great! MYSTI is your AI operating layer.",
        session_id="test",
    )

    assert len(memories) == 1
    assert memories[0].content == "User is working on MYSTI project"

@pytest.mark.asyncio
async def test_extract_disabled():
    mock_llm = AsyncMock()
    extractor = AutoMemoryExtractor(llm=mock_llm, memory=None, enabled=False)

    memories = await extractor.extract_and_store(
        user_message="Test",
        assistant_response="Test",
        session_id="test",
    )

    assert len(memories) == 0
    mock_llm.complete.assert_not_called()
```

---

## Edge Cases

### Classification Fails

```python
async def classify(self, message: str) -> TaskClassification:
    try:
        prompt = self._classification_prompt.format(message=message)
        response = await self.llm.complete([
            {"role": "user", "content": prompt}
        ])
        # Parse response...
    except Exception:
        # Fallback to simple classification
        return self._simple_classify(message)
```

### Model Not Available

```python
def route(self, classification: TaskClassification) -> ModelRouting:
    # Try to route to preferred model
    for model in self.models:
        if classification.complexity == "complex" and "complex" in model.capabilities:
            return ModelRouting(...)

    # Fallback to default model
    return ModelRouting(
        model_id="gpt-4o-mini",
        reason="Fallback: preferred model unavailable",
        ...
    )
```

### Proactive Suggestions Overload

```python
async def get_suggestions(self, ..., limit: int = 5) -> list[ProactiveSuggestion]:
    # ... get suggestions ...

    # Deduplicate by content similarity
    unique_suggestions = []
    seen_content = set()
    for suggestion in suggestions:
        content_hash = hash(suggestion.content[:50])
        if content_hash not in seen_content:
            seen_content.add(content_hash)
            unique_suggestions.append(suggestion)

    return unique_suggestions[:limit]
```

### Auto-Memory Fails

```python
async def extract_and_store(self, user_message, assistant_response, session_id):
    try:
        # ... extraction logic ...
    except Exception as e:
        logger.error(f"Auto-memory extraction failed: {e}")
        return []  # Silent failure, don't break the chat
```

### Streaming Fails

```python
async def chat_stream(self, session_id: str, message: str):
    try:
        # ... streaming logic ...
    except Exception as e:
        # Fallback to non-streaming
        result = await self.chat(session_id, message)
        yield StreamingChunk(
            content=result.response,
            chunk_type="text",
            metadata={},
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
```

---

## Deliverables

When Phase E is complete, you will have:

1. **`src/mysti/engine/task_classifier.py`** — TaskClassifier class
2. **`src/mysti/engine/model_router.py`** — ModelRouter class
3. **`src/mysti/engine/proactive_engine.py`** — ProactiveEngine class
4. **`src/mysti/engine/auto_memory.py`** — AutoMemoryExtractor class
5. **Updated AgentCore** — Uses intelligence components
6. **Streaming support** — SSE for real-time responses
7. **Tests** — 8+ unit tests

---

## What Comes Next

After Phase E, you will move to **Phase F: Polish & Production**, which adds:
- Wire everything together
- Optimize performance
- Full test suite
- Documentation
- Production deployment

Phase E's intelligence layer provides the foundation for a polished, production-ready AI engine.

---

*Phase E makes MYSTI intelligent — it routes models, extracts memories, and proactively helps users.*
