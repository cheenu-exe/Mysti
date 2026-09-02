"""Permission-aware dispatch for MYSTI tools."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from mysti.security.permissions import Permission, PermissionManager, TrustLevel


@dataclass(frozen=True)
class ToolResult:
    success: bool
    output: Any = None
    error: str = ""
    execution_time: float = 0.0
    tool_name: str = ""


class Tool(ABC):
    name: str = "tool"
    description: str = ""
    required_permissions: list[Permission] = []
    min_trust_level: TrustLevel = TrustLevel.T0

    @abstractmethod
    async def execute(self, params: dict) -> ToolResult:
        """Execute a validated operation."""

    def validate_params(self, params: dict) -> bool:
        return isinstance(params, dict)


class ToolGateway:
    _order = {level: index for index, level in enumerate(TrustLevel)}

    def __init__(
        self,
        permissions: PermissionManager | None = None,
        trust_level: TrustLevel = TrustLevel.T0,
        audit=None,
        permission_manager: PermissionManager | None = None,
        current_mode: TrustLevel | None = None,
    ) -> None:
        self.permissions = permissions or permission_manager or PermissionManager()
        self.trust_level = TrustLevel(current_mode or trust_level)
        self.audit = audit
        self._tools: dict[str, Tool] = {}

    def register_tool(self, tool: Tool) -> None:
        if not tool.name:
            raise ValueError("tool name cannot be empty")
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Tool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"unknown tool: {name}") from exc

    def list_tools(self) -> list[dict]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "required_permissions": [p.value for p in t.required_permissions],
                "min_trust_level": t.min_trust_level.value,
            }
            for t in self._tools.values()
        ]

    async def execute(self, tool_name: str, params: dict) -> ToolResult:
        started = time.monotonic()
        try:
            tool = self.get_tool(tool_name)
            if self.trust_level is TrustLevel.T5:
                raise PermissionError("tools are disabled in emergency trust level")
            if self._order[self.trust_level] < self._order[tool.min_trust_level]:
                raise PermissionError(
                    f"{tool_name} requires trust level {tool.min_trust_level.value}"
                )
            missing = [
                p.value
                for p in tool.required_permissions
                if not self.permissions.check_permission(p)
            ]
            if missing:
                raise PermissionError(f"missing permissions: {', '.join(missing)}")
            if not tool.validate_params(params):
                raise ValueError("invalid parameters")
            result = await tool.execute(params)
        except (KeyError, PermissionError, ValueError) as exc:
            result = ToolResult(False, error=str(exc), tool_name=tool_name)
        result = ToolResult(
            result.success, result.output, result.error, time.monotonic() - started, tool_name
        )
        if self.audit is not None:
            self.audit.log(
                "tool.gateway.execute",
                tool_name,
                status="success" if result.success else "failed",
                reason=result.error or None,
                metadata={"tool": tool_name},
            )
        return result
