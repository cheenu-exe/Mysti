"""LLM response cache: caches LLM responses to avoid redundant API calls.

Phase F adds:
- In-memory LRU cache with TTL
- Cache key generation from messages
- Hit/miss tracking
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class CacheStats:
    """Cache performance statistics."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0

    @property
    def total(self) -> int:
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        return self.hits / self.total if self.total > 0 else 0.0


class LLMCache:
    """LRU cache for LLM responses with TTL expiration.

    Caches based on message content and model ID to avoid
    redundant API calls for identical prompts.
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600) -> None:
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._cache: OrderedDict[str, tuple[str, float]] = OrderedDict()
        self._stats = CacheStats()

    def _make_key(self, messages: list[dict[str, str]], model_id: str) -> str:
        """Generate a deterministic cache key from messages and model."""
        content = json.dumps({
            "messages": messages,
            "model": model_id,
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()

    def get(self, messages: list[dict[str, str]], model_id: str) -> str | None:
        """Look up a cached response.

        Returns the cached response if found and not expired, else None.
        """
        key = self._make_key(messages, model_id)

        if key in self._cache:
            response, created_at = self._cache[key]
            if time.time() - created_at < self._ttl:
                # Move to end (most recently used)
                self._cache.move_to_end(key)
                self._stats.hits += 1
                logger.debug("Cache hit for key: %s", key[:12])
                return response
            else:
                # Expired
                del self._cache[key]
                self._stats.evictions += 1

        self._stats.misses += 1
        return None

    def set(self, messages: list[dict[str, str]], model_id: str, response: str) -> None:
        """Store a response in the cache."""
        key = self._make_key(messages, model_id)

        # Evict if at capacity
        if len(self._cache) >= self._max_size and key not in self._cache:
            self._cache.popitem(last=False)
            self._stats.evictions += 1

        self._cache[key] = (response, time.time())
        # Move to end
        self._cache.move_to_end(key)
        logger.debug("Cached response for key: %s", key[:12])

    def invalidate(self, messages: list[dict[str, str]], model_id: str) -> bool:
        """Remove a specific entry from the cache.

        Returns True if the entry was found and removed.
        """
        key = self._make_key(messages, model_id)
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()

    @property
    def stats(self) -> CacheStats:
        """Return cache statistics."""
        return self._stats

    def __len__(self) -> int:
        return len(self._cache)

    def __contains__(self, messages: list[dict[str, str]], model_id: str) -> bool:
        key = self._make_key(messages, model_id)
        if key in self._cache:
            _, created_at = self._cache[key]
            return time.time() - created_at < self._ttl
        return False
