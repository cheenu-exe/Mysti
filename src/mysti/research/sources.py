"""Research source configuration, stored encrypted in remote storage.

The user's research preferences (GitHub repos/topics, arXiv categories, RSS
feeds, Hacker News topic, model-registry toggle) live in one encrypted blob
under the ``meta`` category key at ``mysti/metadata/research_sources.enc``.
Connectors are built from this config; missing or unreadable config falls
back to a conservative default set so the feature works out of the box.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from mysti.exceptions import RecordNotFoundError, ValidationError
from mysti.memory import envelope
from mysti.security.audit import AuditLog
from mysti.security.keys import KeyManager
from mysti.storage.base import StorageBackend

logger = logging.getLogger(__name__)

SOURCE_CONFIG_KEY = "mysti/metadata/research_sources.enc"
SOURCE_CONFIG_AAD = b"mysti:research-sources"
CONFIG_CATEGORY = "meta"

DEFAULT_SOURCE_CONFIG: dict[str, Any] = {
    "github": {
        "repos": [],
        "topics": ["machine-learning", "cybersecurity"],
        "max_repos": 5,
        "enabled": True,
    },
    "arxiv": {
        "query": "",
        "categories": ["cs.CR", "cs.AI", "cs.SE"],
        "max_papers": 10,
        "enabled": True,
    },
    "rss": {"feeds": [], "max_items": 5, "enabled": True},
    "hackernews": {"topic": "", "limit": 30, "max_items": 10, "enabled": True},
    "huggingface": {"max_models": 5, "enabled": True},
}

VALID_KEYS = set(DEFAULT_SOURCE_CONFIG)


class ResearchSourceConfig:
    """Loads, merges and persists the encrypted research source configuration."""

    def __init__(
        self, keys: KeyManager, storage: StorageBackend, audit: AuditLog
    ) -> None:
        self._keys = keys
        self._storage = storage
        self._audit = audit
        self._config: dict[str, Any] | None = None

    async def _config_key(self) -> bytes:
        key, _ = await self._keys.get_category_key(CONFIG_CATEGORY)
        return key

    async def load(self) -> dict[str, Any]:
        """Return the merged configuration (stored values over defaults)."""
        if self._config is not None:
            return self._config
        config = json.loads(json.dumps(DEFAULT_SOURCE_CONFIG))
        try:
            blob = await self._storage.get(SOURCE_CONFIG_KEY)
        except RecordNotFoundError:
            self._config = config
            return config
        try:
            key = await self._config_key()
            stored = json.loads(envelope.decrypt(key, blob, SOURCE_CONFIG_AAD))
        except Exception as exc:  # noqa: BLE001 - fall back on any corruption
            logger.warning("could not decrypt research source config: %s", exc)
            self._config = config
            return config
        for source, values in stored.items():
            if source in VALID_KEYS and isinstance(values, dict):
                config[source].update(values)
        self._config = config
        return config

    async def save(self, config: dict[str, Any]) -> dict[str, Any]:
        """Validate and persist a full source configuration.

        Raises:
            ValidationError: If the config references unknown sources or the
                per-source payloads are not objects.
        """
        unknown = [source for source in config if source not in VALID_KEYS]
        if unknown:
            raise ValidationError(f"unknown research source(s): {', '.join(unknown)}")
        merged = json.loads(json.dumps(DEFAULT_SOURCE_CONFIG))
        for source, values in config.items():
            if not isinstance(values, dict):
                raise ValidationError(f"research source {source!r} must be an object")
            merged[source].update(values)
        key = await self._config_key()
        payload = json.dumps(merged).encode("utf-8")
        await self._storage.put(
            SOURCE_CONFIG_KEY, envelope.encrypt(key, payload, SOURCE_CONFIG_AAD)
        )
        self._config = merged
        self._audit.log("research.sources.save", "sources", metadata={"sources": len(merged)})
        return merged

    async def enabled(self, source: str) -> bool:
        """Return whether ``source`` is enabled in the current config."""
        config = await self.load()
        return bool(config.get(source, {}).get("enabled", True))
