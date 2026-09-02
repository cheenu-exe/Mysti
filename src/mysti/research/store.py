"""Research item store: encrypted, date-partitioned research database.

Every fetched research item is persisted here — sealed with the ``research``
category key into ``mysti/research/items/{date}.enc`` — so collection and
briefing are decoupled from live fetches, and the same story discovered from
two sources is merged instead of stored twice. Cross-date deduplication uses
the ``fingerprint()`` of each item (URL, else source+title).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from mysti.memory import envelope
from mysti.research.models import ResearchItem
from mysti.security.audit import AuditLog
from mysti.security.keys import KeyManager
from mysti.storage.base import StorageBackend

ITEMS_PREFIX = "mysti/research/items/"
ITEMS_KEY_CATEGORY = "research"
DEDUPE_LOOKBACK_DAYS = 30


def _today() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


class ResearchItemStore:
    """Persists research items encrypted per day and deduplicates by identity."""

    def __init__(self, keys: KeyManager, storage: StorageBackend, audit: AuditLog) -> None:
        self._keys = keys
        self._storage = storage
        self._audit = audit

    # ------------------------------------------------------------ key helpers
    async def _research_key(self) -> bytes:
        names = await self._keys.category_names()
        if ITEMS_KEY_CATEGORY not in names:
            await self._keys.create_category(ITEMS_KEY_CATEGORY)
        key, _ = await self._keys.get_category_key(ITEMS_KEY_CATEGORY)
        return key

    def _storage_key(self, date: str) -> str:
        return f"{ITEMS_PREFIX}{date}.enc"

    def _aad(self, date: str) -> bytes:
        return f"mysti:research-items:{date}".encode()

    # ----------------------------------------------------------------- storage
    async def _load_date(self, date: str) -> list[ResearchItem]:
        try:
            blob = await self._storage.get(self._storage_key(date))
        except Exception:  # noqa: BLE001 - a missing date yields no items
            return []
        key = await self._research_key()
        try:
            payload = envelope.decrypt(key, blob, self._aad(date))
            return [ResearchItem.model_validate(item) for item in json.loads(payload)]
        except Exception:  # noqa: BLE001 - corrupt parquet is not fatal
            return []

    async def _save_date(self, date: str, items: list[ResearchItem]) -> None:
        key, version = await self._keys.get_category_key(ITEMS_KEY_CATEGORY)
        payload = json.dumps([item.model_dump() for item in items]).encode("utf-8")
        blob = envelope.seal(key, version, self._aad(date), payload)
        await self._storage.put(self._storage_key(date), blob)

    # ---------------------------------------------------------------- public
    async def store_items(
        self,
        items: list[ResearchItem],
        date: str | None = None,
        lookback_days: int = DEDUPE_LOOKBACK_DAYS,
    ) -> list[ResearchItem]:
        """Persist items for ``date``, deduplicated against recent history.

        Returns the full unique item list stored for that date (existing items
        from the same date plus the newly added ones). Items already known from
        the past ``lookback_days`` are skipped.
        """
        date = date or _today()
        existing = await self._load_date(date)
        known = await self.known_fingerprints(lookback_days)
        seen = {item.fingerprint() for item in existing}
        stored = 0
        for item in items:
            fingerprint = item.fingerprint()
            if fingerprint in seen or fingerprint in known:
                continue
            seen.add(fingerprint)
            existing.append(item)
            stored += 1
        if stored:
            await self._save_date(date, existing)
            self._audit.log(
                "research.items.store",
                date,
                metadata={"stored": stored, "total": len(existing)},
            )
        return existing

    async def items_on(self, date: str | None = None) -> list[dict]:
        """Return stored items for a date (default: today) as plain dicts."""
        date = date or _today()
        return [item.model_dump() for item in await self._load_date(date)]

    async def list_dates(self) -> list[str]:
        """Return dates that have stored items, newest first."""
        try:
            keys = await self._storage.list(ITEMS_PREFIX)
        except Exception:  # noqa: BLE001 - missing prefixes are not fatal
            return []
        dates = [key.removeprefix(ITEMS_PREFIX).removesuffix(".enc") for key in keys]
        return sorted((d for d in dates if d), reverse=True)

    async def known_fingerprints(self, days: int = DEDUPE_LOOKBACK_DAYS) -> set[str]:
        """All item fingerprints stored within the last ``days`` days."""
        fingerprints: set[str] = set()
        for date in await self.list_dates():
            if _date_age_days(date) > days:
                continue
            for item in await self._load_date(date):
                fingerprints.add(item.fingerprint())
        return fingerprints


def _date_age_days(date: str) -> int:
    """Approximate age of ``date`` (YYYY-MM-DD) in days."""
    try:
        parsed = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=UTC)
    except ValueError:
        return 0
    return max(0, (datetime.now(UTC) - parsed).days)
