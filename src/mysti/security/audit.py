"""Append-only, hash-chained audit log.

Records contain no personal content (only action names, resource identifiers
and outcomes). The chain makes tampering detectable via ``verify()``.
Writes are synchronous by design: entries are tiny local appends with no
network I/O, and every service operation must journal durably before returning.
"""

import hashlib
import json
import threading
from datetime import UTC, datetime
from pathlib import Path

_GENESIS_HASH = "0" * 64
_ENTRY_FIELDS = ("seq", "timestamp", "action", "resource", "status", "reason", "metadata")


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


def _entry_digest(prev_hash: str, payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((prev_hash + canonical).encode("utf-8")).hexdigest()


class AuditLog:
    """Local JSONL audit trail with a SHA-256 hash chain."""

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._seq, self._last_hash = self._load_tail()

    def _load_tail(self) -> tuple[int, str]:
        if not self._path.is_file():
            return 0, _GENESIS_HASH
        last_seq, last_hash = 0, _GENESIS_HASH
        with open(self._path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                last_seq = int(record["seq"])
                last_hash = str(record["hash"])
        return last_seq, last_hash

    def log(
        self,
        action: str,
        resource: str,
        status: str = "success",
        reason: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Append one audit entry. Never raises on logging failure beyond I/O errors."""
        with self._lock:
            seq = self._seq + 1
            payload = {
                "seq": seq,
                "timestamp": _iso_now(),
                "action": action,
                "resource": resource,
                "status": status,
                "reason": reason,
                "metadata": metadata or {},
            }
            digest = _entry_digest(self._last_hash, payload)
            record = {**payload, "prev_hash": self._last_hash, "hash": digest}
            with open(self._path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
            self._seq = seq
            self._last_hash = digest

    def verify(self) -> bool:
        """Recompute the full chain and return True if it is intact."""
        expected_prev, expected_seq = _GENESIS_HASH, 0
        if not self._path.is_file():
            return True
        with open(self._path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                expected_seq += 1
                if record.get("prev_hash") != expected_prev or record.get("seq") != expected_seq:
                    return False
                payload = {field: record.get(field) for field in _ENTRY_FIELDS}
                if record.get("hash") != _entry_digest(expected_prev, payload):
                    return False
                expected_prev = record["hash"]
        return True

    def tail(self, limit: int = 50) -> list[dict]:
        """Return the most recent ``limit`` entries, oldest first."""
        if not self._path.is_file():
            return []
        with open(self._path, encoding="utf-8") as handle:
            lines = handle.readlines()
        return [json.loads(line) for line in lines[-limit:] if line.strip()]
