"""Constrained local filesystem operations."""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path

from mysti.security.permissions import Permission, TrustLevel
from mysti.tools.gateway import Tool, ToolResult


class FilesystemTool(Tool):
    name, description = "filesystem", "Read, write, and manage files"
    required_permissions = [Permission.TOOLS_READ, Permission.TOOLS_WRITE]
    min_trust_level = TrustLevel.T1
    max_read_size, max_write_size = 10 * 1024 * 1024, 1024 * 1024

    def _path(self, value: str) -> Path:
        path = Path(os.path.expanduser(value)).resolve()
        text = str(path).lower().replace("\\", "/")
        home = str(Path.home()).lower().replace("\\", "/")
        protected = (
            "/etc",
            "/boot",
            "/sys",
            "/proc",
            f"{home}/.ssh",
            f"{home}/.gnupg",
            f"{home}/.aws",
        )
        if any(text == item or text.startswith(item + "/") for item in protected):
            raise PermissionError("protected path")
        return path

    def read_file(self, path: str) -> str:
        target = self._path(path)
        if target.stat().st_size > self.max_read_size:
            raise ValueError("file exceeds maximum read size")
        return target.read_text(encoding="utf-8")

    def write_file(self, path: str, content: str) -> bool:
        if len(content.encode()) > self.max_write_size:
            raise ValueError("content exceeds maximum write size")
        target = self._path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return True

    def list_directory(self, path: str) -> list[dict]:
        return [
            {"name": p.name, "is_dir": p.is_dir(), "size": p.stat().st_size if p.is_file() else 0}
            for p in self._path(path).iterdir()
        ]

    def search_files(self, path: str, pattern: str) -> list[str]:
        return [
            str(p)
            for p in self._path(path).rglob("*")
            if p.is_file() and fnmatch.fnmatch(p.name, pattern)
        ]

    def get_file_info(self, path: str) -> dict:
        target = self._path(path)
        stat = target.stat()
        return {
            "path": str(target),
            "name": target.name,
            "is_dir": target.is_dir(),
            "size": stat.st_size,
            "modified": stat.st_mtime,
        }

    async def execute(self, params: dict) -> ToolResult:
        try:
            operation = params.get("operation", "")
            args = {k: v for k, v in params.items() if k != "operation"}
            output = getattr(self, operation)(**args)
            return ToolResult(True, output, tool_name=self.name)
        except (OSError, PermissionError, ValueError, TypeError, AttributeError) as exc:
            return ToolResult(False, error=str(exc), tool_name=self.name)
