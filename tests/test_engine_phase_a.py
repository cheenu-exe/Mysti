"""Tests for AI Engine Phase A: Agent Core.

Covers:
- Task classification (LLM-based and rule-based fallback)
- DynamicPromptBuilder
- AgentState
- AgentCore (full pipeline with mocked LLM and memory)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from mysti.engine.core import (
    AgentCore,
    AgentResult,
    TaskClassification,
    _rule_classify,
    classify_task,
)
from mysti.engine.prompt import DynamicPromptBuilder
from mysti.engine.state import AgentState, ToolCall


# ---- Helpers ----


class MockLLM:
    """Deterministic mock LLM for testing."""

    def __init__(self, response: str = "Hello! How can I help?") -> None:
        self._response = response
        self.call_count = 0
        self.last_messages: list[dict[str, str]] = []

    async def complete(self, messages: list[dict[str, str]], **kwargs) -> str:
        self.call_count += 1
        self.last_messages = messages
        return self._response


class MockClassifyLLM:
    """Mock LLM that returns classification JSON."""

    def __init__(self, classification: dict | None = None) -> None:
        self._classification = classification or {
            "intent": "question",
            "complexity": "simple",
            "domain": "general",
            "confidence": 0.9,
            "needs_memory": True,
            "needs_tools": False,
            "needs_knowledge": False,
        }

    async def complete(self, messages: list[dict[str, str]], **kwargs) -> str:
        import json
        return json.dumps(self._classification)


class MockMemory:
    """Mock memory service for testing."""

    def __init__(self, results: list | None = None) -> None:
        self._results = results or []
        self.search_calls: list[tuple[str, int]] = []

    async def search(self, query: str, limit: int = 5) -> list:
        self.search_calls.append((query, limit))
        return self._results


class MockSearchHit:
    """Mock search hit."""

    def __init__(self, id: str, preview: str, score: float) -> None:
        self.id = id
        self.preview = preview
        self.score = score


# ---- TaskClassification tests ----


class TestTaskClassification:
    def test_dataclass_fields(self):
        tc = TaskClassification(
            intent="question",
            complexity="simple",
            domain="general",
            confidence=0.9,
        )
        assert tc.intent == "question"
        assert tc.needs_memory is True
        assert tc.needs_tools is False

    def test_custom_fields(self):
        tc = TaskClassification(
            intent="command",
            complexity="complex",
            domain="code",
            confidence=0.8,
            needs_memory=False,
            needs_tools=True,
            needs_knowledge=True,
        )
        assert tc.needs_tools is True
        assert tc.needs_knowledge is True


# ---- Rule-based classification tests ----


class TestRuleClassify:
    def test_question_how(self):
        tc = _rule_classify("How do I use this?")
        assert tc.intent == "question"

    def test_question_mark(self):
        tc = _rule_classify("Is this working?")
        assert tc.intent == "question"

    def test_command_do(self):
        tc = _rule_classify("do the backup now")
        assert tc.intent == "command"

    def test_command_run(self):
        tc = _rule_classify("run the tests")
        assert tc.intent == "command"

    def test_research_intent(self):
        tc = _rule_classify("research the latest AI papers")
        assert tc.intent == "research"

    def test_discussion_fallback(self):
        tc = _rule_classify("tell me about your day")
        assert tc.intent == "discussion"

    def test_simple_complexity(self):
        tc = _rule_classify("hello")
        assert tc.complexity == "simple"

    def test_medium_complexity(self):
        tc = _rule_classify("what is the current status of my projects and how are they progressing")
        assert tc.complexity == "medium"

    def test_complex_complexity(self):
        tc = _rule_classify("I need a comprehensive and thorough analysis of all my research papers including detailed citations and cross-references between them and how they relate to my current projects and ongoing work")
        assert tc.complexity == "complex"

    def test_code_domain(self):
        tc = _rule_classify("help me debug this function")
        assert tc.domain == "code"

    def test_memory_domain(self):
        tc = _rule_classify("remember that I prefer dark mode")
        assert tc.domain == "memory"

    def test_research_domain(self):
        tc = _rule_classify("find papers about transformers")
        assert tc.domain == "research"

    def test_general_domain(self):
        tc = _rule_classify("what's the weather like")
        assert tc.domain == "general"


# ---- LLM classification tests ----


class TestClassifyTask:
    @pytest.mark.asyncio
    async def test_classify_with_llm(self):
        llm = MockClassifyLLM()
        tc = await classify_task(llm, "How do I use this?")
        assert tc.intent == "question"
        assert tc.complexity == "simple"

    @pytest.mark.asyncio
    async def test_classify_fallback_on_error(self):
        class FailingLLM:
            async def complete(self, messages, **kwargs):
                raise RuntimeError("LLM unavailable")

        tc = await classify_task(FailingLLM(), "How do I use this?")
        assert tc.intent == "question"  # rule-based fallback


# ---- DynamicPromptBuilder tests ----


class TestDynamicPromptBuilder:
    def test_default_base_prompt(self):
        builder = DynamicPromptBuilder()
        prompt = builder.build()
        assert "MYSTI" in prompt
        assert "private" in prompt

    def test_custom_base_prompt(self):
        builder = DynamicPromptBuilder(base_system_prompt="Custom base")
        prompt = builder.build()
        assert prompt.startswith("Custom base")

    def test_add_section(self):
        builder = DynamicPromptBuilder(base_system_prompt="Base")
        builder.add_section("Section 1")
        prompt = builder.build()
        assert "Section 1" in prompt

    def test_empty_section_ignored(self):
        builder = DynamicPromptBuilder(base_system_prompt="Base")
        builder.add_section("")
        builder.add_section("   ")
        prompt = builder.build()
        assert prompt == "Base"

    def test_multiple_sections(self):
        builder = DynamicPromptBuilder(base_system_prompt="Base")
        builder.add_section("Section A")
        builder.add_section("Section B")
        prompt = builder.build()
        assert "Section A" in prompt
        assert "Section B" in prompt

    def test_add_memory_context(self):
        builder = DynamicPromptBuilder(base_system_prompt="Base")
        builder.add_memory_context(["memory 1", "memory 2"])
        prompt = builder.build()
        assert "Relevant Memories" in prompt
        assert "memory 1" in prompt
        assert "memory 2" in prompt

    def test_add_memory_context_empty(self):
        builder = DynamicPromptBuilder(base_system_prompt="Base")
        builder.add_memory_context([])
        prompt = builder.build()
        assert "Relevant Memories" not in prompt

    def test_add_tool_definitions(self):
        builder = DynamicPromptBuilder(base_system_prompt="Base")
        builder.add_tool_definitions(["search: search the web", "read: read a file"])
        prompt = builder.build()
        assert "Available Tools" in prompt
        assert "search: search the web" in prompt

    def test_add_knowledge_context(self):
        builder = DynamicPromptBuilder(base_system_prompt="Base")
        builder.add_knowledge_context("## Entities\\n- MYSTI (project)")
        prompt = builder.build()
        assert "Entities" in prompt


# ---- AgentState tests ----


class TestAgentState:
    def test_create_state(self):
        state = AgentState(session_id="test-123")
        assert state.session_id == "test-123"
        assert state.messages == []

    def test_add_message(self):
        state = AgentState(session_id="test")
        state.add_message("user", "hello")
        assert len(state.messages) == 1
        assert state.messages[0]["role"] == "user"
        assert state.messages[0]["content"] == "hello"

    def test_add_tool_call(self):
        state = AgentState(session_id="test")
        call = ToolCall(tool_name="search", arguments={"q": "test"}, result="found", success=True)
        state.add_tool_call(call)
        assert len(state.tool_calls) == 1
        assert state.tool_calls[0].tool_name == "search"

    def test_to_context_messages(self):
        state = AgentState(session_id="test")
        state.add_message("user", "hello")
        state.add_message("assistant", "hi there")
        ctx = state.to_context_messages()
        assert len(ctx) == 2
        assert ctx[0]["role"] == "user"

    def test_to_context_messages_trims(self):
        state = AgentState(session_id="test")
        # Add many long messages
        for i in range(20):
            state.add_message("user", f"message {i} " + "x" * 200)
        ctx = state.to_context_messages(max_tokens=10)
        assert len(ctx) < 20

    def test_get_user_messages(self):
        state = AgentState(session_id="test")
        state.add_message("user", "hello")
        state.add_message("assistant", "hi")
        state.add_message("user", "bye")
        users = state.get_user_messages()
        assert len(users) == 2

    def test_get_assistant_messages(self):
        state = AgentState(session_id="test")
        state.add_message("user", "hello")
        state.add_message("assistant", "hi")
        state.add_message("assistant", "hello again")
        assistants = state.get_assistant_messages()
        assert len(assistants) == 2

    def test_last_user_message(self):
        state = AgentState(session_id="test")
        assert state.last_user_message() is None
        state.add_message("user", "first")
        state.add_message("assistant", "response")
        state.add_message("user", "second")
        assert state.last_user_message() == "second"


# ---- AgentCore tests ----


class TestAgentCore:
    @pytest.mark.asyncio
    async def test_new_session(self):
        llm = MockLLM()
        core = AgentCore(llm=llm)
        session_id = core.new_session()
        assert session_id
        assert session_id in core._sessions

    @pytest.mark.asyncio
    async def test_get_state_creates(self):
        llm = MockLLM()
        core = AgentCore(llm=llm)
        state = core.get_state("new-session")
        assert state.session_id == "new-session"

    @pytest.mark.asyncio
    async def test_chat_basic(self):
        llm = MockLLM(response="I can help with that!")
        core = AgentCore(llm=llm)
        result = await core.chat("session-1", "Hello!")

        assert isinstance(result, AgentResult)
        assert result.session_id == "session-1"
        assert result.response == "I can help with that!"
        assert len(result.messages) == 2  # user + assistant
        assert result.classification is not None

    @pytest.mark.asyncio
    async def test_chat_classifies(self):
        llm = MockClassifyLLM()
        core = AgentCore(llm=llm)
        result = await core.chat("s1", "How do I use this?")

        assert result.classification is not None
        assert result.classification.intent == "question"

    @pytest.mark.asyncio
    async def test_chat_with_memory(self):
        llm = MockLLM(response="Based on your memories...")
        hits = [MockSearchHit("m1", "User prefers dark mode", 0.9)]
        memory = MockMemory(results=hits)
        core = AgentCore(llm=llm, memory=memory)

        result = await core.chat("s1", "What do I prefer?")

        assert len(result.memories_used) == 1
        assert "dark mode" in result.memories_used[0]
        assert memory.search_calls[0][0] == "What do I prefer?"

    @pytest.mark.asyncio
    async def test_chat_memory_disabled_when_not_needed(self):
        llm = MockClassifyLLM(classification={
            "intent": "command",
            "complexity": "simple",
            "domain": "general",
            "confidence": 0.9,
            "needs_memory": False,
            "needs_tools": False,
            "needs_knowledge": False,
        })
        memory = MockMemory()
        core = AgentCore(llm=llm, memory=memory)

        await core.chat("s1", "run the tests")
        assert len(memory.search_calls) == 0

    @pytest.mark.asyncio
    async def test_chat_no_memory_service(self):
        llm = MockLLM()
        core = AgentCore(llm=llm, memory=None)
        result = await core.chat("s1", "hello")
        assert result.memories_used == []

    @pytest.mark.asyncio
    async def test_chat_conversation_continuity(self):
        llm = MockLLM()
        core = AgentCore(llm=llm)

        await core.chat("s1", "hello")
        result = await core.chat("s1", "how are you?")

        state = core.get_state("s1")
        assert len(state.messages) == 4  # 2 user + 2 assistant

    @pytest.mark.asyncio
    async def test_chat_steps_recorded(self):
        llm = MockLLM()
        core = AgentCore(llm=llm)
        result = await core.chat("s1", "test")

        step_names = [s["step"] for s in result.steps]
        assert "classify" in step_names
        assert "llm_call" in step_names

    @pytest.mark.asyncio
    async def test_chat_llm_error_handled(self):
        class FailingLLM:
            async def complete(self, messages, **kwargs):
                raise RuntimeError("LLM is down")

        core = AgentCore(llm=FailingLLM())
        result = await core.chat("s1", "hello")
        assert "error" in result.response.lower()

    @pytest.mark.asyncio
    async def test_chat_metadata(self):
        llm = MockLLM()
        core = AgentCore(llm=llm)
        result = await core.chat("s1", "hello")
        state = core.get_state("s1")
        assert "last_classification" in state.metadata
