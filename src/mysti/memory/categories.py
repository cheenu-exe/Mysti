"""Memory categories: default taxonomy plus user-defined categories.

Category *configuration* (descriptions, default priority, default tags) is
stored as an encrypted blob in remote storage; the *keys* for custom
categories live in the wrapped key manifest. Defaults are always present and
cannot be deleted.
"""

import json

from mysti.exceptions import ValidationError
from mysti.memory import envelope
from mysti.memory.consolidation import CONSOLIDATION_HISTORY_AAD, CONSOLIDATION_HISTORY_KEY
from mysti.memory.service import MemoryService
from mysti.security.audit import AuditLog
from mysti.security.keys import KeyManager
from mysti.storage.base import StorageBackend

CATEGORY_CONFIG_KEY = "mysti/metadata/category_config.enc"
CATEGORY_CONFIG_AAD = b"mysti:category-config"

DEFAULT_CATEGORIES: dict[str, dict] = {
    "personal": {
        "name": "personal",
        "description": "Personal information, preferences, life events",
        "priority": 5,
        "tags": ["personal"],
    },
    "projects": {
        "name": "projects",
        "description": "Current and past projects, goals, tasks",
        "priority": 7,
        "tags": ["projects"],
    },
    "relationships": {
        "name": "relationships",
        "description": "People, connections, interactions",
        "priority": 6,
        "tags": ["people"],
    },
    "technical": {
        "name": "technical",
        "description": "Technical knowledge, code snippets, solutions",
        "priority": 6,
        "tags": ["technical"],
    },
    "research": {
        "name": "research",
        "description": "Papers, articles, insights, analysis",
        "priority": 5,
        "tags": ["research"],
    },
    "ideas": {
        "name": "ideas",
        "description": "Ideas, brainstorms, plans, inventions",
        "priority": 4,
        "tags": ["ideas"],
    },
}


class CategoryManager:
    """Manages category configuration and per-category statistics."""

    def __init__(
        self,
        memory: MemoryService,
        keys: KeyManager,
        storage: StorageBackend,
        audit: AuditLog,
    ) -> None:
        self._memory = memory
        self._keys = keys
        self._storage = storage
        self._audit = audit

    async def _load_config(self) -> dict[str, dict]:
        config = {name: dict(spec) for name, spec in DEFAULT_CATEGORIES.items()}
        try:
            blob = await self._storage.get(CATEGORY_CONFIG_KEY)
        except Exception:
            return config
        if blob is None:
            return config
        key, _ = await self._keys.get_category_key("meta")
        try:
            stored = json.loads(envelope.decrypt(key, blob, CATEGORY_CONFIG_AAD))
        except (KeyError, ValueError):
            return config
        for name, spec in stored.items():
            if name not in config:
                config[name] = spec
        return config

    async def get_category(self, name: str) -> dict:
        """Return the configuration for ``name``.

        Raises:
            ValidationError: If the category does not exist.
        """
        config = await self._load_config()
        if name not in config:
            raise ValidationError(f"unknown category: {name!r}")
        return config[name]

    async def list_categories(self) -> list[dict]:
        """List all categories with their live record counts."""
        config = await self._load_config()
        counts = await self._memory.list_categories()
        return [
            {
                **spec,
                "count": counts.get(name, 0),
                "is_default": name in DEFAULT_CATEGORIES,
            }
            for name, spec in sorted(config.items())
        ]

    async def create_category(self, name: str, config: dict) -> dict:
        """Create a custom category (new wrapped key + stored configuration).

        Raises:
            ValidationError: If the name is invalid or already exists.
        """
        name = (name or "").strip().lower()
        if not name or len(name) > 64:
            raise ValidationError("category name must be 1-64 characters")
        existing = await self._load_config()
        if name in existing:
            raise ValidationError(f"category already exists: {name!r}")
        spec = {
            "name": name,
            "description": str(config.get("description", "")),
            "priority": max(1, min(10, int(config.get("priority", 5)))),
            "tags": [str(tag) for tag in config.get("tags", [])],
        }
        await self._keys.create_category(name)
        existing[name] = spec
        await self._save_custom(existing)
        self._audit.log("categories.create", name)
        return spec

    async def delete_category(self, name: str) -> None:
        """Remove a custom category; default categories cannot be deleted.

        Raises:
            ValidationError: For default or unknown categories, or when
                records still exist in the category.
        """
        if name in DEFAULT_CATEGORIES:
            raise ValidationError(f"default category {name!r} cannot be deleted")
        config = await self._load_config()
        if name not in config:
            raise ValidationError(f"unknown category: {name!r}")
        counts = await self._memory.list_categories()
        if counts.get(name, 0) > 0:
            raise ValidationError(
                f"category {name!r} still holds {counts[name]} records; "
                "move or delete them first"
            )
        del config[name]
        await self._save_custom(config)
        self._audit.log("categories.delete", name)

    async def get_stats(self) -> dict:
        """Knowledge-base statistics across categories.

        Extends :meth:`MemoryService.stats` with usage counters: the total
        number of searches (from the audit log), how many conversation
        summaries exist on the remote store and when the last consolidation
        job completed.
        """
        memory_stats = await self._memory.stats()
        config = await self._load_config()
        per_category: dict[str, dict] = {}
        for name in sorted(config):
            bucket = memory_stats["categories"].get(name, {})
            per_category[name] = {
                "count": bucket.get("count", 0),
                "bytes": bucket.get("bytes", 0),
                "avg_importance": bucket.get("avg_importance", 0),
                "priority": config[name].get("priority", 5),
                "oldest": bucket.get("oldest"),
                "newest": bucket.get("newest"),
            }
        return {
            "total_records": memory_stats["total_records"],
            "total_size_bytes": memory_stats["total_size_bytes"],
            "avg_record_size": memory_stats["avg_record_size"],
            "oldest_record": memory_stats["oldest_record"],
            "newest_record": memory_stats["newest_record"],
            "searches": await self._count_search_events(),
            "summaries": len(await self._storage.list("mysti/summaries/")),
            "last_consolidation": await self._last_consolidation(),
            "categories": per_category,
        }

    async def _save_custom(self, config: dict[str, dict]) -> None:
        custom = {
            name: spec
            for name, spec in config.items()
            if name not in DEFAULT_CATEGORIES
        }
        key, _ = await self._keys.get_category_key("meta")
        payload = json.dumps(custom).encode("utf-8")
        await self._storage.put(
            CATEGORY_CONFIG_KEY,
            envelope.encrypt(key, payload, CATEGORY_CONFIG_AAD),
        )

    async def _count_search_events(self) -> int:
        """Count ``memory.search`` events in the local audit log."""
        try:
            path = self._audit._path  # noqa: SLF001 - local journal, read-only access
        except AttributeError:
            return 0
        if not path.is_file():
            return 0
        count = 0
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    if line.startswith('{"action": "memory.search"') or '"memory.search"' in line:
                        count += 1
                except ValueError:
                    continue
        return count

    async def _last_consolidation(self) -> dict | None:
        """Return the most recent completed consolidation job, if any."""
        try:
            blob = await self._storage.get(CONSOLIDATION_HISTORY_KEY)
        except Exception:  # noqa: BLE001 - missing history is not an error
            return None
        if blob is None:
            return None
        try:
            key, _ = await self._keys.get_category_key("meta")
            history = json.loads(envelope.decrypt(key, blob, CONSOLIDATION_HISTORY_AAD))
        except Exception:  # noqa: BLE001 - a corrupt history is not fatal
            return None
        completed = [job for job in history if job.get("status") == "completed"]
        if not completed:
            return None
        completed.sort(key=lambda job: job.get("started_at", ""), reverse=True)
        return completed[0]
