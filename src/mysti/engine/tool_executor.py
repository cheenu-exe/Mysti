"""Tool executor: executes registered tools with permission checks and error handling.

Phase C implements:
- Tool execution with timeout
- Permission gating
- Result wrapping with success/failure tracking
- Integration with ToolRegistry
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from mysti.engine.tool_registry import ToolDefinition, ToolRegistry

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """Result of a tool execution."""

    tool_name: str
    success: bool
    output: str
    error: str | None = None
    duration_ms: float = 0.0
    arguments: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize for logging or storage."""
        return {
            "tool_name": self.tool_name,
            "success": self.success,
            "output": self.output[:500],  # truncate for logging
            "error": self.error,
            "duration_ms": self.duration_ms,
        }


class ToolExecutor:
    """Executes tools from a ToolRegistry with safety checks.

    Features:
    - Timeout enforcement
    - Permission gating (optional callback)
    - Error handling and logging
    - Result tracking
    """

    def __init__(
        self,
        registry: ToolRegistry,
        default_timeout: float = 30.0,
        permission_checker: Any = None,
    ) -> None:
        self.registry = registry
        self.default_timeout = default_timeout
        self.permission_checker = permission_checker
        self._execution_history: list[ToolResult] = []

    async def _check_permission(self, tool: ToolDefinition) -> bool:
        """Check if tool execution is permitted."""
        if not tool.requires_permission:
            return True
        if self.permission_checker is None:
            # No permission checker = deny by default for permission-requiring tools
            logger.warning("No permission checker configured for tool: %s", tool.name)
            return False
        try:
            return await self.permission_checker.check(tool.name)
        except Exception as exc:
            logger.error("Permission check failed for %s: %s", tool.name, exc)
            return False

    async def execute(
        self,
        tool_name: str,
        arguments: dict | None = None,
    ) -> ToolResult:
        """Execute a tool by name with given arguments.

        Args:
            tool_name: Name of the tool to execute.
            arguments: Arguments to pass to the tool function.

        Returns:
            ToolResult with success status, output, and metadata.
        """
        arguments = arguments or {}
        start_time = time.monotonic()

        # Look up tool
        tool = self.registry.get(tool_name)
        if tool is None:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                output="",
                error=f"Unknown tool: {tool_name}",
                arguments=arguments,
            )

        # Validate arguments
        is_valid, error_msg = self.registry.validate_arguments(tool_name, arguments)
        if not is_valid:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                output="",
                error=f"Invalid arguments: {error_msg}",
                arguments=arguments,
            )

        # Check permissions
        if not await self._check_permission(tool):
            return ToolResult(
                tool_name=tool_name,
                success=False,
                output="",
                error="Permission denied",
                arguments=arguments,
            )

        # Execute with timeout
        timeout = tool.timeout_seconds or self.default_timeout
        try:
            result = await asyncio.wait_for(
                tool.func(**arguments),
                timeout=timeout,
            )
            duration_ms = (time.monotonic() - start_time) * 1000
            tool_result = ToolResult(
                tool_name=tool_name,
                success=True,
                output=str(result),
                duration_ms=round(duration_ms, 2),
                arguments=arguments,
            )
        except asyncio.TimeoutError:
            duration_ms = (time.monotonic() - start_time) * 1000
            tool_result = ToolResult(
                tool_name=tool_name,
                success=False,
                output="",
                error=f"Tool execution timed out after {timeout}s",
                duration_ms=round(duration_ms, 2),
                arguments=arguments,
            )
        except Exception as exc:
            duration_ms = (time.monotonic() - start_time) * 1000
            tool_result = ToolResult(
                tool_name=tool_name,
                success=False,
                output="",
                error=f"Tool execution failed: {exc}",
                duration_ms=round(duration_ms, 2),
                arguments=arguments,
            )

        # Track history
        self._execution_history.append(tool_result)
        logger.info(
            "Tool executed: %s (success=%s, duration=%.1fms)",
            tool_name,
            tool_result.success,
            tool_result.duration_ms,
        )

        return tool_result

    async def execute_from_llm_response(
        self,
        tool_call_json: str,
    ) -> ToolResult:
        """Parse and execute a tool call from LLM function-calling output.

        Expects JSON with 'name' and 'arguments' keys.
        """
        try:
            data = json.loads(tool_call_json)
            tool_name = data.get("name", "")
            arguments = data.get("arguments", {})
        except (json.JSONDecodeError, KeyError) as exc:
            return ToolResult(
                tool_name="",
                success=False,
                output="",
                error=f"Failed to parse tool call JSON: {exc}",
            )

        return await self.execute(tool_name, arguments)

    def get_history(self) -> list[ToolResult]:
        """Return the execution history."""
        return list(self._execution_history)

    def clear_history(self) -> None:
        """Clear the execution history."""
        self._execution_history.clear()

    def format_tools_for_prompt(self) -> str:
        """Delegate to registry for formatting tools for LLM prompt."""
        return self.registry.format_tools_for_prompt()

    def get_function_schemas(self) -> list[dict]:
        """Delegate to registry for OpenAI function schemas."""
        return self.registry.get_function_schemas()
