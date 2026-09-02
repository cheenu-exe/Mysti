"""Composition helpers for gateway tools."""

from __future__ import annotations
import asyncio
from mysti.tools.gateway import ToolResult, ToolGateway


class ToolComposer:
    def __init__(self, gateway: ToolGateway):
        self.gateway = gateway

    async def compose(self, steps: list[dict]) -> ToolResult:
        output = None
        for step in steps:
            params = dict(step.get("params", {}))
            if output is not None:
                params.setdefault("input", output)
            result = await self.gateway.execute(step["tool"], params)
            if not result.success:
                return result
            output = result.output
        return ToolResult(True, output, tool_name="composition")

    async def parallel(self, tasks: list[dict]) -> list[ToolResult]:
        return await asyncio.gather(
            *(self.gateway.execute(task["tool"], task.get("params", {})) for task in tasks)
        )
