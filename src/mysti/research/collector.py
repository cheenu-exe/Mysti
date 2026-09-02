"""Research collector: fetches from every enabled source and persists items.

Encapsulates one research cycle: for each configured connector, fetch items,
then store them (deduplicated against recent history) in the encrypted
research item store. The daily briefing and the scheduler both run the
collector so "collect" and "present" stay decoupled.
"""

from __future__ import annotations

from mysti.research.connectors import SourceConnector
from mysti.research.models import ResearchItem
from mysti.research.sources import ResearchSourceConfig
from mysti.research.store import ResearchItemStore
from mysti.security.audit import AuditLog


class ResearchCollector:
    """Runs a full research cycle: fetch -> normalize -> persist."""

    def __init__(
        self,
        connectors: list[SourceConnector],
        sources: ResearchSourceConfig,
        store: ResearchItemStore,
        audit: AuditLog,
    ) -> None:
        self._connectors = connectors
        self._sources = sources
        self._store = store
        self._audit = audit

    async def collect(self, date: str | None = None) -> dict:
        """Fetch every enabled source and persist items for ``date``.

        Returns summary stats: ``items_scanned`` (raw fetch count), ``stored``
        (new items written), ``duplicates`` (already-known items skipped) and
        ``sources_checked``.
        """
        all_items: list[ResearchItem] = []
        sources_checked = 0
        for connector in self._connectors:
            sources_checked += 1
            try:
                items = await connector.fetch()
            except Exception:  # noqa: BLE001 - never let one source break the cycle
                items = []
            all_items.extend(items)

        stored = await self._store.store_items(all_items, date=date)

        result = {
            "items_scanned": len(all_items),
            "stored": sum(
                1 for item in all_items if item.fingerprint() in {i.fingerprint() for i in stored}
            ) if all_items else 0,
            "items_total": len(stored),
            "sources_checked": sources_checked,
        }
        result["duplicates"] = max(0, result["items_scanned"] - result["stored"])
        self._audit.log(
            "research.collect",
            date or "today",
            metadata={k: v for k, v in result.items()},
        )
        return result
