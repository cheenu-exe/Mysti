"""Permission and trust-mode controls for MYSTI."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Callable


class Permission(StrEnum):
    MEMORY_READ = "memory.read"
    MEMORY_WRITE = "memory.write"
    MEMORY_DELETE = "memory.delete"
    RESEARCH_READ = "research.read"
    RESEARCH_WRITE = "research.write"
    TOOLS_READ = "tools.read"
    TOOLS_WRITE = "tools.write"
    TOOLS_EXECUTE = "tools.execute"
    ADMIN_KEY = "admin.key"
    ADMIN_CONFIG = "admin.config"


class TrustLevel(StrEnum):
    T0 = "T0"
    T1 = "T1"
    T2 = "T2"
    T3 = "T3"
    T4 = "T4"
    T5 = "T5"


class PermissionManager:
    def __init__(self) -> None:
        self._permissions: dict[Permission, datetime | None] = {}
        self._emergency = False

    def check_permission(self, permission: Permission) -> bool:
        if self._emergency:
            return False
        expiry = self._permissions.get(Permission(permission))
        if expiry is None and Permission(permission) not in self._permissions:
            return False
        if expiry is not None and datetime.now(UTC) >= expiry:
            self._permissions.pop(Permission(permission), None)
            return False
        return True

    def grant_permission(self, permission: Permission, expires_in: timedelta | None = None) -> None:
        self._permissions[Permission(permission)] = (
            datetime.now(UTC) + expires_in if expires_in is not None else None
        )

    def revoke_permission(self, permission: Permission) -> None:
        self._permissions.pop(Permission(permission), None)

    def list_permissions(self) -> list[dict]:
        return [
            {"permission": p.value, "expires_at": expiry.isoformat() if expiry else None}
            for p, expiry in self._permissions.items()
            if self.check_permission(p)
        ]

    def emergency_revoke_all(self) -> None:
        self._permissions.clear()
        self._emergency = True


_MODE_PERMISSIONS = {
    TrustLevel.T0: [],
    TrustLevel.T1: [Permission.MEMORY_READ, Permission.MEMORY_WRITE, Permission.RESEARCH_READ],
    TrustLevel.T2: [
        Permission.MEMORY_READ,
        Permission.MEMORY_WRITE,
        Permission.RESEARCH_READ,
        Permission.TOOLS_READ,
    ],
    TrustLevel.T3: [
        p for p in Permission if p not in (Permission.ADMIN_KEY, Permission.ADMIN_CONFIG)
    ],
    TrustLevel.T4: list(Permission),
    TrustLevel.T5: [Permission.ADMIN_KEY, Permission.ADMIN_CONFIG],
}


class ModeManager:
    def __init__(
        self, path: Path | None = None, confirm: Callable[[str], bool] | None = None
    ) -> None:
        self.path = Path(path or Path.home() / ".config" / "mysti" / "mode.json")
        self.confirm = confirm or (lambda _prompt: False)
        self._mode = self._load()

    def _load(self) -> TrustLevel:
        try:
            return TrustLevel(json.loads(self.path.read_text(encoding="utf-8"))["mode"])
        except (OSError, ValueError, KeyError):
            return TrustLevel.T0

    def get_current_mode(self) -> TrustLevel:
        return self._mode

    def set_mode(self, level: TrustLevel) -> bool:
        level = TrustLevel(level)
        transition = level in (TrustLevel.T3, TrustLevel.T4) and level is not self._mode
        if transition:
            prompt = (
                "Allow network write access?"
                if level is TrustLevel.T3
                else "Allow automatic execution?"
            )
            if not self.confirm(prompt):
                return False
        self._mode = level
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"mode": level.value}), encoding="utf-8")
        return True

    def get_mode_permissions(self, level: TrustLevel) -> list[Permission]:
        return list(_MODE_PERMISSIONS[TrustLevel(level)])
