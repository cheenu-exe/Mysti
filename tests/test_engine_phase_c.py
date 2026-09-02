"""Tests for AI Engine Phase C: Tool Integration.

Covers:
- ToolRegistry (register, lookup, validation, formatting)
- ToolExecutor (execution, timeout, permissions, error handling)
- ToolDefinition (schema generation, prompt formatting)
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from mysti.engine.tool_executor import ToolExecutor, ToolResult
from mysti.engine.tool_registry import (
    ToolDefinition,
    ToolParameter,
    ToolRegistry,
)


# ---- Helpers ----


async def mock_search_tool(query: str = "test") -> str:
    """Mock search tool."""
    return f"Results for: {query}"


async def mock_add_tool(a: int = 0, b: int = 0) -> str:
    """Mock add tool."""
    return str(a + b)


async def mock_slow_tool(delay: float = 5.0) -> str:
    """Mock tool that takes a long time."""
    await asyncio.sleep(delay)
    return "done"


async def mock_failing_tool() -> str:
    """Mock tool that always fails."""
    raise ValueError("Tool execution failed")


class MockPermissionChecker:
    """Mock permission checker for testing."""

    def __init__(self, allowed: bool = True) -> None:
        self.allowed = allowed
        self.check_calls: list[str] = []

    async def check(self, tool_name: str) -> bool:
        self.check_calls.append(tool_name)
        return self.allowed


# ---- ToolParameter tests ----


class TestToolParameter:
    def test_to_schema_string(self):
        param = ToolParameter(name="query", type="string", description="Search query", required=True)
        schema = param.to_schema()
        assert schema["type"] == "string"
        assert schema["description"] == "Search query"

    def test_to_schema_with_enum(self):
        param = ToolParameter(name="mode", type="string", enum=["fast", "slow"])
        schema = param.to_schema()
        assert schema["enum"] == ["fast", "slow"]

    def test_to_schema_with_default(self):
        param = ToolParameter(name="limit", type="integer", default=10)
        schema = param.to_schema()
        assert schema["default"] == 10


# ---- ToolDefinition tests ----


class TestToolDefinition:
    def test_to_function_schema(self):
        tool = ToolDefinition(
            name="search",
            description="Search the web",
            parameters=[
                ToolParameter(name="query", type="string", required=True, description="Search query"),
                ToolParameter(name="limit", type="integer", default=10),
            ],
            func=mock_search_tool,
        )
        schema = tool.to_function_schema()
        assert schema["name"] == "search"
        assert schema["description"] == "Search the web"
        assert "query" in schema["parameters"]["properties"]
        assert "query" in schema["parameters"]["required"]
        assert "limit" in schema["parameters"]["properties"]

    def test_format_for_prompt(self):
        tool = ToolDefinition(
            name="search",
            description="Search the web",
            parameters=[
                ToolParameter(name="query", type="string", required=True, description="Search query"),
            ],
            func=mock_search_tool,
        )
        text = tool.format_for_prompt()
        assert "search" in text
        assert "Search the web" in text
        assert "query" in text
        assert "[required]" in text

    def test_format_for_prompt_no_params(self):
        tool = ToolDefinition(
            name="ping",
            description="Ping server",
            parameters=[],
            func=mock_search_tool,
        )
        text = tool.format_for_prompt()
        assert "ping" in text
        assert "Ping server" in text


# ---- ToolRegistry tests ----


class TestToolRegistry:
    def test_register_and_get(self):
        registry = ToolRegistry()
        tool = ToolDefinition(
            name="search",
            description="Search",
            parameters=[],
            func=mock_search_tool,
        )
        registry.register(tool)
        assert registry.get("search") is tool

    def test_get_unknown(self):
        registry = ToolRegistry()
        assert registry.get("nonexistent") is None

    def test_register_function(self):
        registry = ToolRegistry()
        registry.register_function(
            name="add",
            func=mock_add_tool,
            description="Add two numbers",
            parameters=[
                ToolParameter(name="a", type="integer"),
                ToolParameter(name="b", type="integer"),
            ],
        )
        assert "add" in registry

    def test_list_tools(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="a", description="A", parameters=[], func=mock_search_tool))
        registry.register(ToolDefinition(name="b", description="B", parameters=[], func=mock_search_tool))
        tools = registry.list_tools()
        assert len(tools) == 2

    def test_list_names(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="a", description="A", parameters=[], func=mock_search_tool))
        registry.register(ToolDefinition(name="b", description="B", parameters=[], func=mock_search_tool))
        names = registry.list_names()
        assert "a" in names
        assert "b" in names

    def test_list_by_category(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="a", description="A", parameters=[], func=mock_search_tool, category="search"))
        registry.register(ToolDefinition(name="b", description="B", parameters=[], func=mock_search_tool, category="file"))
        search_tools = registry.list_by_category("search")
        assert len(search_tools) == 1
        assert search_tools[0].name == "a"

    def test_format_tools_for_prompt(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(
            name="search",
            description="Search",
            parameters=[ToolParameter(name="q", type="string", required=True)],
            func=mock_search_tool,
        ))
        text = registry.format_tools_for_prompt()
        assert "Available Tools" in text
        assert "search" in text

    def test_format_tools_empty(self):
        registry = ToolRegistry()
        assert registry.format_tools_for_prompt() == ""

    def test_get_function_schemas(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(
            name="search",
            description="Search",
            parameters=[ToolParameter(name="q", type="string", required=True)],
            func=mock_search_tool,
        ))
        schemas = registry.get_function_schemas()
        assert len(schemas) == 1
        assert schemas[0]["name"] == "search"

    def test_validate_arguments_valid(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(
            name="search",
            description="Search",
            parameters=[ToolParameter(name="q", type="string", required=True)],
            func=mock_search_tool,
        ))
        is_valid, error = registry.validate_arguments("search", {"q": "test"})
        assert is_valid is True

    def test_validate_arguments_missing_required(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(
            name="search",
            description="Search",
            parameters=[ToolParameter(name="q", type="string", required=True)],
            func=mock_search_tool,
        ))
        is_valid, error = registry.validate_arguments("search", {})
        assert is_valid is False
        assert "q" in error

    def test_validate_arguments_unknown_tool(self):
        registry = ToolRegistry()
        is_valid, error = registry.validate_arguments("nonexistent", {})
        assert is_valid is False
        assert "Unknown" in error

    def test_validate_arguments_enum(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(
            name="mode",
            description="Set mode",
            parameters=[ToolParameter(name="m", type="string", enum=["a", "b"])],
            func=mock_search_tool,
        ))
        is_valid, _ = registry.validate_arguments("mode", {"m": "a"})
        assert is_valid is True
        is_valid, error = registry.validate_arguments("mode", {"m": "c"})
        assert is_valid is False

    def test_len_and_contains(self):
        registry = ToolRegistry()
        assert len(registry) == 0
        registry.register(ToolDefinition(name="a", description="A", parameters=[], func=mock_search_tool))
        assert len(registry) == 1
        assert "a" in registry
        assert "b" not in registry

    def test_overwrite_existing(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="a", description="v1", parameters=[], func=mock_search_tool))
        registry.register(ToolDefinition(name="a", description="v2", parameters=[], func=mock_search_tool))
        assert registry.get("a").description == "v2"


# ---- ToolExecutor tests ----


class TestToolExecutor:
    @pytest.mark.asyncio
    async def test_execute_basic(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(
            name="search",
            description="Search",
            parameters=[ToolParameter(name="query", type="string")],
            func=mock_search_tool,
        ))
        executor = ToolExecutor(registry)
        result = await executor.execute("search", {"query": "hello"})

        assert result.success is True
        assert "Results for: hello" in result.output
        assert result.tool_name == "search"
        assert result.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self):
        executor = ToolExecutor(ToolRegistry())
        result = await executor.execute("nonexistent")
        assert result.success is False
        assert "Unknown" in result.error

    @pytest.mark.asyncio
    async def test_execute_invalid_args(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(
            name="search",
            description="Search",
            parameters=[ToolParameter(name="q", type="string", required=True)],
            func=mock_search_tool,
        ))
        executor = ToolExecutor(registry)
        result = await executor.execute("search", {})
        assert result.success is False
        assert "Invalid arguments" in result.error

    @pytest.mark.asyncio
    async def test_execute_timeout(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(
            name="slow",
            description="Slow tool",
            parameters=[],
            func=mock_slow_tool,
            timeout_seconds=0.1,
        ))
        executor = ToolExecutor(registry)
        result = await executor.execute("slow")
        assert result.success is False
        assert "timed out" in result.error

    @pytest.mark.asyncio
    async def test_execute_exception(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(
            name="failing",
            description="Failing tool",
            parameters=[],
            func=mock_failing_tool,
        ))
        executor = ToolExecutor(registry)
        result = await executor.execute("failing")
        assert result.success is False
        assert "failed" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_permission_denied(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(
            name="protected",
            description="Protected tool",
            parameters=[],
            func=mock_search_tool,
            requires_permission=True,
        ))
        checker = MockPermissionChecker(allowed=False)
        executor = ToolExecutor(registry, permission_checker=checker)
        result = await executor.execute("protected")
        assert result.success is False
        assert "Permission denied" in result.error

    @pytest.mark.asyncio
    async def test_execute_permission_granted(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(
            name="protected",
            description="Protected tool",
            parameters=[],
            func=mock_search_tool,
            requires_permission=True,
        ))
        checker = MockPermissionChecker(allowed=True)
        executor = ToolExecutor(registry, permission_checker=checker)
        result = await executor.execute("protected")
        assert result.success is True
        assert "protected" in checker.check_calls

    @pytest.mark.asyncio
    async def test_execute_no_permission_checker(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(
            name="protected",
            description="Protected tool",
            parameters=[],
            func=mock_search_tool,
            requires_permission=True,
        ))
        executor = ToolExecutor(registry)  # No permission checker
        result = await executor.execute("protected")
        assert result.success is False
        assert "Permission denied" in result.error

    @pytest.mark.asyncio
    async def test_execute_history(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="a", description="A", parameters=[], func=mock_search_tool))
        executor = ToolExecutor(registry)
        await executor.execute("a")
        await executor.execute("a")
        history = executor.get_history()
        assert len(history) == 2

    @pytest.mark.asyncio
    async def test_clear_history(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="a", description="A", parameters=[], func=mock_search_tool))
        executor = ToolExecutor(registry)
        await executor.execute("a")
        executor.clear_history()
        assert len(executor.get_history()) == 0

    @pytest.mark.asyncio
    async def test_execute_from_llm_response(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(
            name="search",
            description="Search",
            parameters=[ToolParameter(name="query", type="string")],
            func=mock_search_tool,
        ))
        executor = ToolExecutor(registry)
        result = await executor.execute_from_llm_response(
            '{"name": "search", "arguments": {"query": "test"}}'
        )
        assert result.success is True
        assert "Results for: test" in result.output

    @pytest.mark.asyncio
    async def test_execute_from_llm_response_invalid_json(self):
        executor = ToolExecutor(ToolRegistry())
        result = await executor.execute_from_llm_response("not json")
        assert result.success is False
        assert "parse" in result.error.lower()

    @pytest.mark.asyncio
    async def test_format_tools_for_prompt(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="search", description="Search", parameters=[], func=mock_search_tool))
        executor = ToolExecutor(registry)
        text = executor.format_tools_for_prompt()
        assert "Available Tools" in text

    @pytest.mark.asyncio
    async def test_get_function_schemas(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="search", description="Search", parameters=[], func=mock_search_tool))
        executor = ToolExecutor(registry)
        schemas = executor.get_function_schemas()
        assert len(schemas) == 1

    @pytest.mark.asyncio
    async def test_tool_result_to_dict(self):
        result = ToolResult(
            tool_name="search",
            success=True,
            output="results",
            duration_ms=12.5,
        )
        d = result.to_dict()
        assert d["tool_name"] == "search"
        assert d["success"] is True
        assert d["duration_ms"] == 12.5
