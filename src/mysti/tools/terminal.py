"""Terminal operations routed through the Phase 3 sandbox."""

from __future__ import annotations
import asyncio
import uuid
from mysti.security.permissions import Permission, TrustLevel
from mysti.security.sandbox import SandboxManager
from mysti.tools.gateway import Tool, ToolResult


class TerminalTool(Tool):
    name, description = "terminal", "Execute shell commands"
    required_permissions = [Permission.TOOLS_EXECUTE]
    min_trust_level = TrustLevel.T2

    def __init__(
        self, sandbox: SandboxManager | None = None, trust_level: TrustLevel = TrustLevel.T2
    ):
        self.sandbox, self.trust_level, self._jobs = (
            sandbox or SandboxManager(),
            TrustLevel(trust_level),
            {},
        )

    async def execute(self, params: dict | str) -> ToolResult:
        try:
            if isinstance(params, str):
                params = {"command": params}
            result = await self.execute_command(params["command"], params.get("timeout", 30))
            return ToolResult(
                not result.blocked and result.return_code == 0,
                result,
                result.block_reason,
                tool_name=self.name,
            )
        except (KeyError, ValueError, asyncio.TimeoutError) as exc:
            return ToolResult(False, error=str(exc), tool_name=self.name)

    async def execute_command(self, command: str, timeout: int = 30):
        return await asyncio.wait_for(
            self.sandbox.run_in_sandbox(command, self.trust_level), timeout=max(1, timeout)
        )

    async def execute_background(self, command: str) -> str:
        job_id = uuid.uuid4().hex
        self._jobs[job_id] = asyncio.create_task(self.execute_command(command))
        return job_id

    async def get_job_status(self, job_id: str) -> dict:
        task = self._jobs[job_id]
        if not task.done():
            return {"job_id": job_id, "status": "running"}
        return {"job_id": job_id, "status": "completed", "result": task.result()}

    async def kill_job(self, job_id: str) -> bool:
        task = self._jobs.get(job_id)
        if task is None:
            return False
        task.cancel()
        return True
