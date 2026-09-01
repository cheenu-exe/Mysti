"""RAM-only cache for encrypted blobs.

Holds ciphertext exclusively (never plaintext), bounded by total byte size,
with per-entry TTL and LRU eviction. The cache disappears when the process
exits; nothing is ever written to disk from here.
"""

import time
from collections import OrderedDict


class BlobCache:
    """Bounded LRU cache with TTL, storing ciphertext blobs only."""

    def __init__(self, max_bytes: int, ttl_seconds: float) -> None:
        self._max_bytes = max_bytes
        self._ttl = ttl_seconds
        self._entries: OrderedDict[str, tuple[bytes, float]] = OrderedDict()
        self._current_bytes = 0

    def get(self, key: str) -> bytes | None:
        entry = self._entries.pop(key, None)
        if entry is None:
            return None
        blob, expires_at = entry
        if time.monotonic() > expires_at:
            self._current_bytes -= len(blob)
            return None
        self._entries[key] = entry
        return blob

    def put(self, key: str, blob: bytes) -> None:
        if len(blob) > self._max_bytes:
            return
        self._drop(key)
        self._evict_expired()
        while self._current_bytes + len(blob) > self._max_bytes and self._entries:
            _, (evicted, _) = self._entries.popitem(last=False)
            self._current_bytes -= len(evicted)
        self._entries[key] = (blob, time.monotonic() + self._ttl)
        self._current_bytes += len(blob)

    def _drop(self, key: str) -> None:
        entry = self._entries.pop(key, None)
        if entry is not None:
            self._current_bytes -= len(entry[0])

    def _evict_expired(self) -> None:
        now = time.monotonic()
        expired = [key for key, (_, expires_at) in self._entries.items() if now > expires_at]
        for key in expired:
            self._drop(key)

    def delete(self, key: str) -> None:
        self._drop(key)

    def clear(self) -> None:
        self._entries.clear()
        self._current_bytes = 0

    def stats(self) -> dict[str, int]:
        return {
            "entries": len(self._entries),
            "bytes": self._current_bytes,
            "max_bytes": self._max_bytes,
        }
