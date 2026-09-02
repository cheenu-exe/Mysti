"""Daily briefing: gather -> score -> summarize, stored encrypted per day.

Briefings are sealed with the ``research`` category key and persisted at
``mysti/briefings/{date}.enc`` in remote storage, so they sync everywhere the
user's storage backend does and never touch disk in plaintext.
"""

import json
from datetime import UTC, datetime
from typing import Any

from mysti.exceptions import RecordNotFoundError
from mysti.memory import envelope
from mysti.research.connectors import SourceConnector
from mysti.research.models import ResearchItem
from mysti.research.relevance import RelevanceEngine
from mysti.security.audit import AuditLog
from mysti.security.keys import KeyManager
from mysti.storage.base import StorageBackend

BRIEFING_PREFIX = "mysti/briefings/"
BRIEFING_KEY_CATEGORY = "research"

# Buckets used to group highlights in the briefing document.
TOPIC_BUCKETS: dict[str, list[str]] = {
    "cybersecurity": ["security", "cve", "exploit", "malware", "ctf", "vulnerability",
                      "cybersecurity", "encryption", "threat", "breach", "cs.cr"],
    "ai/ml": ["machine learning", "llm", "neural", "deep learning", "transformer",
              "cs.ai", "cs.lg"],
    "development": ["devops", "developer", "programming", "open source", "api",
                    "framework", "release", "library", "cs.se", "devsecops"],
}


def _today() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


class DailyBriefing:
    """Generates, stores and retrieves encrypted daily briefings."""

    def __init__(
        self,
        connectors: list[SourceConnector],
        relevance: RelevanceEngine,
        keys: KeyManager,
        storage: StorageBackend,
        audit: AuditLog,
        *,
        min_score: float = 5.0,
    ) -> None:
        self._connectors = connectors
        self._relevance = relevance
        self._keys = keys
        self._storage = storage
        self._audit = audit
        self._min_score = min_score

    # ----------------------------------------------------------------- storage
    async def _research_key(self) -> bytes:
        names = await self._keys.category_names()
        if BRIEFING_KEY_CATEGORY not in names:
            await self._keys.create_category(BRIEFING_KEY_CATEGORY)
        key, _ = await self._keys.get_category_key(BRIEFING_KEY_CATEGORY)
        return key

    def _storage_key(self, date: str) -> str:
        return f"{BRIEFING_PREFIX}{date}.enc"

    async def _save(self, briefing: dict[str, Any]) -> None:
        key = await self._research_key()
        date = briefing["date"]
        payload = json.dumps(briefing).encode("utf-8")
        await self._storage.put(
            self._storage_key(date),
            envelope.encrypt(key, payload, f"mysti:briefing:{date}".encode()),
        )
        self._audit.log("briefing.save", date)

    async def _load(self, date: str) -> dict[str, Any]:
        key = await self._research_key()
        blob = await self._storage.get(self._storage_key(date))
        return json.loads(envelope.decrypt(key, blob, f"mysti:briefing:{date}".encode()))

    def _bucket_for(self, item: ResearchItem) -> str:
        haystack = (
            f"{item.title} {item.content} "
            f"{' '.join(item.metadata.get('categories', []))}"
        ).lower()
        for bucket, markers in TOPIC_BUCKETS.items():
            if any(marker in haystack for marker in markers):
                return bucket
        return "general"

    def _summarize(self, highlights: list[dict], scanned: int) -> str:
        """Deterministic plain-language overview (no LLM required)."""
        if not highlights:
            return f"Scanned {scanned} items; nothing met the relevance threshold today."
        by_source: dict[str, int] = {}
        for highlight in highlights:
            by_source[highlight["source"]] = by_source.get(highlight["source"], 0) + 1
        parts = [f"{count} from {source}" for source, count in sorted(by_source.items())]
        top = highlights[0]
        return (
            f"Scanned {scanned} items and selected {len(highlights)} "
            f"({', '.join(parts)}). Top story: {top['title']}."
        )

    # ---------------------------------------------------------------- generate
    async def generate_briefing(self, date: str | None = None) -> dict[str, Any]:
        """Fetch from every source, score/filter/dedupe and build the brief."""
        date = date or _today()
        all_items: list[ResearchItem] = []
        sources_checked = 0
        for connector in self._connectors:
            sources_checked += 1
            try:
                items = await connector.fetch()
            except Exception:  # never let one source break the briefing
                items = []
            all_items.extend(items)

        deduped = await self._relevance.deduplicate(all_items)
        ranked = await self._relevance.rank(deduped)
        scored = await self._relevance.score_all(ranked)
        selected = [(s, i) for s, i in scored if s >= self._min_score][:20]

        highlights = [
            {
                "title": item.title,
                "source": item.source,
                "relevance": round(score, 2),
                "url": item.url,
                "author": item.author,
                "published_at": item.published_at,
                "bucket": self._bucket_for(item),
            }
            for score, item in selected
        ]

        categories: dict[str, list[dict]] = {}
        for highlight in highlights:
            bucket = highlight["bucket"] if isinstance(highlight["bucket"], str) else "general"
            categories.setdefault(bucket, []).append(highlight)

        briefing = {
            "date": date,
            "summary": self._summarize(highlights, len(all_items)),
            "highlights": highlights,
            "categories": categories,
            "stats": {
                "items_scanned": len(all_items),
                "items_selected": len(highlights),
                "sources_checked": sources_checked,
            },
        }
        await self._save(briefing)
        return briefing

    # --------------------------------------------------------------- retrieval
    async def get_briefing(self, date: str | None = None) -> dict[str, Any]:
        """Retrieve a stored briefing by date (default: today)."""
        date = date or _today()
        try:
            return await self._load(date)
        except RecordNotFoundError:
            if date == _today():
                return await self.generate_briefing(date)
            raise

    async def list_briefings(self, days: int = 7) -> list[dict[str, Any]]:
        """List the most recent ``days`` stored briefings (newest first)."""
        try:
            keys = await self._storage.list(BRIEFING_PREFIX)
        except Exception:
            keys = []
        briefings: list[dict[str, Any]] = []
        for storage_key in sorted(keys, reverse=True):
            if len(briefings) >= days:
                break
            date = storage_key.removeprefix(BRIEFING_PREFIX).removesuffix(".enc")
            try:
                briefing = await self._load(date)
            except Exception:
                continue
            briefings.append(
                {
                    "date": briefing["date"],
                    "summary": briefing.get("summary", ""),
                    "items_selected": briefing.get("stats", {}).get("items_selected", 0),
                }
            )
        return briefings
