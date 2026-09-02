"""Conservative command safety checks and restricted command execution."""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass

from mysti.security.permissions import TrustLevel


@dataclass(frozen=True)
class SafetyCheck:
    is_safe: bool
    risk_level: str
    reason: str


@dataclass(frozen=True)
class SandboxResult:
    command: str
    stdout: str
    stderr: str
    return_code: int
    execution_time: float
    blocked: bool = False
    block_reason: str = ""


class SandboxManager:
    _blocked = (
        (r"rm\s+-rf\s+/(?:\s|$)", "recursive deletion of root"),
        (r"sudo\s+rm", "privileged deletion"),
        (r"chmod\s+777", "unsafe permissions"),
        (r"(?:curl|wget)[^|]*\|\s*(?:sh|bash)", "download and execute pipeline"),
        (r"/etc/(?:passwd|shadow)\b", "protected system file access"),
        (r"(?:~[/\\]|[/\\]home[/\\][^/\\]+[/\\])\.(?:ssh|gnupg)\b", "key file access"),
    )
    _network = re.compile(
        r"\b(?:curl|wget|nc|netcat|ssh|scp|ftp|ping|nslookup|dig)\b|https?://", re.I
    )
    _write_network = re.compile(r"\b(?:-X\s*(?:POST|PUT|DELETE|PATCH)|--upload|scp|rsync)\b", re.I)

    async def check_safety(self, command: str) -> SafetyCheck:
        for pattern, reason in self._blocked:
            if re.search(pattern, command, re.I):
                return SafetyCheck(False, "critical", reason)
        return SafetyCheck(True, "low", "no dangerous patterns detected")

    async def run_in_sandbox(self, command: str, level: TrustLevel) -> SandboxResult:
        started = time.monotonic()
        level = TrustLevel(level)
        safety = await self.check_safety(command)
        reason = safety.reason
        allowed = safety.is_safe
        if level in (TrustLevel.T0, TrustLevel.T5):
            allowed, reason = False, "command execution is disabled in this trust level"
        elif self._network.search(command) and level is TrustLevel.T1:
            allowed, reason = False, "network access is disabled in T1"
        elif (
            self._network.search(command)
            and level is TrustLevel.T2
            and self._write_network.search(command)
        ):
            allowed, reason = False, "network writes require T3 or higher"
        if not allowed:
            return SandboxResult(command, "", reason, 126, time.monotonic() - started, True, reason)
        try:
            process = await asyncio.create_subprocess_shell(
                command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            return SandboxResult(
                command,
                stdout.decode(errors="replace"),
                stderr.decode(errors="replace"),
                process.returncode or 0,
                time.monotonic() - started,
            )
        except OSError as exc:
            return SandboxResult(command, "", str(exc), 126, time.monotonic() - started)
