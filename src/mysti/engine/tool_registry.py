"""Tool registry: manages available tools and their definitions.

Phase C implements:
- Tool definition with schema validation
- Tool registration and lookup
- Tool description formatting for LLM prompts
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

logger = logging.getLogger(__name__)


class ToolFunc(Protocol):
    """Protocol for tool implementation functions."""

    async def __call__(self, **kwargs: Any) -> str: ...


@dataclass
class ToolParameter:
    """Definition of a single tool parameter."""

    name: str
    type: str  # "string", "integer", "boolean", "array", "object"
    description: str = ""
    required: bool = False
    default: Any = None
    enum: list[Any] | None = None

    def to_schema(self) -> dict:
        """Convert to JSON Schema property format."""
        schema: dict[str, Any] = {"type": self.type}
        if self.description:
            schema["description"] = self.description
        if self.enum:
            schema["enum"] = self.enum
        if self.default is not None:
            schema["default"] = self.default
        return schema


@dataclass
class ToolDefinition:
    """Complete definition of a callable tool."""

    name: str
    description: str
    parameters: list[ToolParameter]
    func: ToolFunc
    category: str = "general"
    requires_permission: bool = False
    timeout_seconds: float = 30.0

    def to_function_schema(self) -> dict:
        """Convert to OpenAI function-calling schema format."""
        properties = {}
        required = []
        for param in self.parameters:
            properties[param.name] = param.to_schema()
            if param.required:
                required.append(param.name)

        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }

    def format_for_prompt(self) -> str:
        """Format tool description for inclusion in system prompt."""
        param_lines = []
        for p in self.parameters:
            req = " [required]" if p.required else ""
            default = f" (default: {p.default})" if p.default is not None else ""
            param_lines.append(f"  - {p.name}: {p.type}{req}{default} — {p.description}")

        lines = [f"**{self.name}**: {self.description}"]
        if param_lines:
            lines.append("  Parameters:")
            lines.extend(param_lines)
        return "\n".join(lines)


class ToolRegistry:
    """Registry of available tools with lookup and validation."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        """Register a tool. Overwrites if name already exists."""
        self._tools[tool.name] = tool
        logger.debug("Registered tool: %s", tool.name)

    def register_function(
        self,
        name: str,
        func: ToolFunc,
        description: str,
        parameters: list[ToolParameter] | None = None,
        **kwargs: Any,
    ) -> None:
        """Convenience: register a function as a tool."""
        tool = ToolDefinition(
            name=name,
            description=description,
            parameters=parameters or [],
            func=func,
            **kwargs,
        )
        self.register(tool)

    def get(self, name: str) -> ToolDefinition | None:
        """Look up a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[ToolDefinition]:
        """Return all registered tools."""
        return list(self._tools.values())

    def list_names(self) -> list[str]:
        """Return all registered tool names."""
        return list(self._tools.keys())

    def list_by_category(self, category: str) -> list[ToolDefinition]:
        """Return tools filtered by category."""
        return [t for t in self._tools.values() if t.category == category]

    def format_tools_for_prompt(self) -> str:
        """Format all tools for inclusion in system prompt."""
        tools = self.list_tools()
        if not tools:
            return ""
        lines = ["## Available Tools"]
        for tool in tools:
            lines.append(tool.format_for_prompt())
        return "\n\n".join(lines)

    def get_function_schemas(self) -> list[dict]:
        """Return all tools as OpenAI function schemas."""
        return [tool.to_function_schema() for tool in self.list_tools()]

    def validate_arguments(self, tool_name: str, arguments: dict) -> tuple[bool, str]:
        """Validate arguments against tool's parameter schema.

        Returns (is_valid, error_message).
        """
        tool = self.get(tool_name)
        if tool is None:
            return False, f"Unknown tool: {tool_name}"

        for param in tool.parameters:
            if param.required and param.name not in arguments:
                return False, f"Missing required parameter: {param.name}"

            if param.name in arguments:
                value = arguments[param.name]
                if param.enum and value not in param.enum:
                    return False, f"Parameter '{param.name}' must be one of: {param.enum}"

        return True, ""

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools
