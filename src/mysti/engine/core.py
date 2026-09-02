"""Agent core: the main agent loop with task classification and memory-aware generation.

Phase A implements:
- AgentState management per session
- Task classification (intent, complexity, domain)
- Dynamic prompt building with memory context
- Multi-step agent loop with LLM calls
- Memory search integration for context enhancement
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

from mysti.engine.prompt import DynamicPromptBuilder
from mysti.engine.state import AgentState, ToolCall

logger = logging.getLogger(__name__)

MAX_AGENT_STEPS = 10


# ---- Protocols (dependency interfaces) ----


class LLMClient(Protocol):
    """Minimal LLM interface required by the agent."""

    async def complete(self, messages: list[dict[str, str]], **kwargs: Any) -> str: ...


class MemorySearchResult(Protocol):
    """A single memory search hit."""

    @property
    def id(self) -> str: ...
    @property
    def preview(self) -> str: ...
    @property
    def score(self) -> float: ...


class MemoryService(Protocol):
    """Memory service search interface."""

    async def search(self, query: str, limit: int = 5) -> list[MemorySearchResult]: ...


# ---- Task classification ----


@dataclass
class TaskClassification:
    """Result of classifying a user message."""

    intent: str  # "question", "command", "discussion", "research"
    complexity: str  # "simple", "medium", "complex"
    domain: str  # "general", "code", "research", "memory"
    confidence: float
    needs_memory: bool = True
    needs_tools: bool = False
    needs_knowledge: bool = False


_CLASSIFY_PROMPT = """\
Classify the following user message into a JSON object with these fields:
- intent: one of "question", "command", "discussion", "research"
- complexity: one of "simple", "medium", "complex"
- domain: one of "general", "code", "research", "memory"
- confidence: float 0.0-1.0
- needs_memory: bool (does this benefit from memory context?)
- needs_tools: bool (does this likely need tool usage?)
- needs_knowledge: bool (does this benefit from knowledge graph?)

User message: {message}

Return ONLY the JSON object, no other text."""


async def classify_task(llm: LLMClient, message: str) -> TaskClassification:
    """Classify a user message using the LLM.

    Falls back to a rule-based classifier if the LLM fails or is unavailable.
    """
    try:
        response = await llm.complete([{"role": "user", "content": _CLASSIFY_PROMPT.format(message=message)}])
        data = json.loads(response)
        return TaskClassification(
            intent=data.get("intent", "discussion"),
            complexity=data.get("complexity", "medium"),
            domain=data.get("domain", "general"),
            confidence=float(data.get("confidence", 0.7)),
            needs_memory=bool(data.get("needs_memory", True)),
            needs_tools=bool(data.get("needs_tools", False)),
            needs_knowledge=bool(data.get("needs_knowledge", False)),
        )
    except Exception:
        logger.debug("LLM classification failed, using rule-based fallback")
        return _rule_classify(message)


def _rule_classify(message: str) -> TaskClassification:
    """Simple rule-based classification as fallback."""
    lower = message.lower().strip()

    # intent
    if any(lower.startswith(w) for w in ("how", "what", "why", "when", "where", "who", "is ", "are ", "can ")):
        intent = "question"
    elif "?" in message:
        intent = "question"
    elif any(lower.startswith(w) for w in ("do ", "run ", "execute ", "create ", "delete ", "write ")):
        intent = "command"
    elif any(w in lower for w in ("research", "find ", "search ", "look up")):
        intent = "research"
    else:
        intent = "discussion"

    # complexity
    word_count = len(message.split())
    if word_count < 8:
        complexity = "simple"
    elif word_count < 25:
        complexity = "medium"
    else:
        complexity = "complex"

    # domain
    if any(w in lower for w in ("code", "function", "class", "api", "bug", "debug")):
        domain = "code"
    elif any(w in lower for w in ("memory", "remember", "recall", "forget")):
        domain = "memory"
    elif any(w in lower for w in ("research", "find", "search", "paper", "article")):
        domain = "research"
    else:
        domain = "general"

    return TaskClassification(
        intent=intent,
        complexity=complexity,
        domain=domain,
        confidence=0.6,
        needs_memory=True,
        needs_tools=intent == "command",
        needs_knowledge=domain == "research",
    )


# ---- Agent result ----


@dataclass
class AgentResult:
    """Result of an agent interaction."""

    session_id: str
    response: str
    messages: list[dict[str, str]]
    steps: list[dict[str, Any]]
    total_tokens: int
    tools_used: list[str]
    memories_used: list[str]
    classification: TaskClassification | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ---- Agent core ----


class AgentCore:
    """Main agent: manages sessions, classifies tasks, retrieves memory, generates responses.

    The agent loop:
    1. Classify the user's intent
    2. Retrieve relevant memories (if needed)
    3. Build a dynamic prompt with context
    4. Call the LLM
    5. Return the response

    Optional hooks for tool execution and knowledge graph are not yet wired
    (coming in Phases C and D).
    """

    def __init__(
        self,
        llm: LLMClient,
        memory: MemoryService | None = None,
        max_steps: int = MAX_AGENT_STEPS,
    ) -> None:
        self.llm = llm
        self.memory = memory
        self.max_steps = max_steps
        self._sessions: dict[str, AgentState] = {}

    def get_state(self, session_id: str) -> AgentState:
        """Get or create agent state for a session."""
        if session_id not in self._sessions:
            self._sessions[session_id] = AgentState(session_id=session_id)
        return self._sessions[session_id]

    def new_session(self) -> str:
        """Create a new session and return its ID."""
        import uuid
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = AgentState(session_id=session_id)
        return session_id

    async def _retrieve_memories(self, query: str, limit: int = 5) -> list[str]:
        """Search memory for relevant context."""
        if self.memory is None:
            return []
        try:
            hits = await self.memory.search(query, limit=limit)
            return [hit.preview for hit in hits]
        except Exception:
            logger.debug("Memory search failed, continuing without memory context")
            return []

    async def chat(self, session_id: str, message: str) -> AgentResult:
        """Process a user message through the full agent pipeline.

        Steps:
        1. Classify the task
        2. Retrieve memories (if needed)
        3. Build system prompt with context
        4. Call LLM
        5. Return result
        """
        state = self.get_state(session_id)
        state.add_message("user", message)

        steps: list[dict[str, Any]] = []
        total_tokens = 0
        tools_used: list[str] = []

        # Step 1: Classify
        classification = await classify_task(self.llm, message)
        state.metadata["last_classification"] = classification
        steps.append({
            "step": "classify",
            "intent": classification.intent,
            "complexity": classification.complexity,
            "domain": classification.domain,
        })

        # Step 2: Retrieve memories
        memories_used: list[str] = []
        memory_context: list[str] = []
        if classification.needs_memory and self.memory:
            memory_context = await self._retrieve_memories(message)
            memories_used = memory_context
            state.memories_used.extend(memories_used)
            steps.append({"step": "memory_retrieve", "count": len(memory_context)})

        # Step 3: Build prompt
        builder = DynamicPromptBuilder()
        if memory_context:
            builder.add_memory_context(memory_context)

        system_prompt = builder.build()
        messages = [{"role": "system", "content": system_prompt}] + state.to_context_messages()

        # Step 4: LLM call
        try:
            response = await self.llm.complete(messages)
            total_tokens += len(response) // 4  # rough estimate
        except Exception as exc:
            response = f"I encountered an error: {exc}"
            logger.error("LLM call failed: %s", exc)

        state.add_message("assistant", response)
        steps.append({"step": "llm_call", "tokens_estimate": total_tokens})

        return AgentResult(
            session_id=session_id,
            response=response,
            messages=state.messages,
            steps=steps,
            total_tokens=total_tokens,
            tools_used=tools_used,
            memories_used=memories_used,
            classification=classification,
        )

    async def close(self) -> None:
        """Release resources."""
        pass
