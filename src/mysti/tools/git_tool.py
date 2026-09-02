"""Git repository operations using the git CLI."""

from __future__ import annotations
import asyncio
from mysti.security.permissions import Permission, TrustLevel
from mysti.tools.gateway import Tool, ToolResult


class GitTool(Tool):
    name, description = "git", "Git repository operations"
    required_permissions = [Permission.TOOLS_READ, Permission.TOOLS_WRITE]
    min_trust_level = TrustLevel.T2

    async def _run(self, repo: str, *args: str) -> str:
        proc = await asyncio.create_subprocess_exec(
            "git", *args, cwd=repo, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        out, err = await proc.communicate()
        if proc.returncode:
            raise RuntimeError(err.decode(errors="replace").strip())
        return out.decode(errors="replace")

    async def status(self, repo_path: str) -> dict:
        return {"output": await self._run(repo_path, "status", "--short")}

    async def diff(self, repo_path: str, file: str | None = None) -> str:
        return await self._run(repo_path, "diff", *(["--", file] if file else []))

    async def log(self, repo_path: str, limit: int = 10) -> list[dict]:
        return [
            {"commit": line.split(" ", 1)[0], "message": line.split(" ", 1)[1]}
            for line in (
                await self._run(repo_path, "log", f"-{limit}", "--pretty=format:%H %s")
            ).splitlines()
            if " " in line
        ]

    async def commit(self, repo_path: str, message: str) -> bool:
        await self._run(repo_path, "commit", "-m", message)
        return True

    async def branch_list(self, repo_path: str) -> list[str]:
        return [
            x.strip("* ") for x in (await self._run(repo_path, "branch", "--list")).splitlines()
        ]

    async def execute(self, params: dict) -> ToolResult:
        try:
            return ToolResult(
                True, await getattr(self, params.pop("operation"))(**params), tool_name=self.name
            )
        except Exception as exc:
            return ToolResult(False, error=str(exc), tool_name=self.name)
