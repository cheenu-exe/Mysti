"""Memory service: the only layer where plaintext records exist (transiently).

Store/retrieve/search/delete/list operations. Content is sealed with the
category key before upload; the remote index is encrypted with the reserved
``meta`` category key and holds no content or plaintext metadata.
"""

import hashlib
import json
import uuid
from datetime import UTC, datetime

from mysti.exceptions import RecordNotFoundError, ValidationError
from mysti.memory import envelope
from mysti.memory.cache import BlobCache
from mysti.memory.models import IndexEntry, MemoryRecord, SearchHit
from mysti.security.audit import AuditLog
from mysti.security.keys import KeyManager
from mysti.storage.base import StorageBackend

INDEX_KEY = "mysti/memories/index.enc"
INDEX_AAD = b"mysti:memory-index"


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


def record_path(record_id: str, category: str) -> str:
    """Remote storage path for a memory record blob."""
    return f"mysti/memories/{category}/{record_id}.enc"


class MemoryService:
    """Encrypted personal memory storage with a remote ciphertext archive."""

    def __init__(
        self,
        storage: StorageBackend,
        keys: KeyManager,
        cache: BlobCache,
        audit: AuditLog,
        max_record_bytes: int = 1024 * 1024,
    ) -> None:
        self._storage = storage
        self._keys = keys
        self._cache = cache
        self._audit = audit
        self._max_record_bytes = max_record_bytes

    async def _load_index(self) -> list[IndexEntry]:
        try:
            blob = await self._storage.get(INDEX_KEY)
        except RecordNotFoundError:
            return []
        key, _ = await self._keys.get_category_key("meta")
        data = envelope.decrypt(key, blob, INDEX_AAD)
        return [IndexEntry.model_validate(item) for item in json.loads(data)]

    async def _save_index(self, entries: list[IndexEntry]) -> None:
        key, _ = await self._keys.get_category_key("meta")
        payload = json.dumps([entry.model_dump() for entry in entries]).encode("utf-8")
        await self._storage.put(INDEX_KEY, envelope.encrypt(key, payload, INDEX_AAD))

    def _find_entry(self, entries: list[IndexEntry], record_id: str) -> IndexEntry:
        for entry in entries:
            if entry.id == record_id:
                return entry
        raise RecordNotFoundError(f"record not found: {record_id}")

    async def _decrypt_entry(self, entry: IndexEntry) -> str:
        path = record_path(entry.id, entry.category)
        blob = self._cache.get(path)
        if blob is None:
            blob = await self._storage.get(path)
            self._cache.put(path, blob)
        key, _ = await self._keys.get_category_key(entry.category, entry.key_version)
        plaintext, _ = envelope.unseal(key, envelope.record_aad(entry.id, entry.category), blob)
        return plaintext.decode("utf-8")

    # --- public API (store/retrieve defined here; search/delete below) ---

    async def store(
        self, category: str, content: str, metadata: dict | None = None
    ) -> MemoryRecord:
        """Encrypt ``content`` locally and upload it; returns the new record."""
        known = await self._keys.category_names()
        if category not in known or category in ("meta", "conversation"):
            raise ValidationError(f"unknown memory category: {category!r}")
        content_bytes = content.encode("utf-8")
        if len(content_bytes) > self._max_record_bytes:
            raise ValidationError(f"record exceeds maximum size of {self._max_record_bytes} bytes")
        record_id = str(uuid.uuid4())
        now = _iso_now()
        key, version = await self._keys.get_category_key(category)
        blob = envelope.seal(key, version, envelope.record_aad(record_id, category), content_bytes)
        path = record_path(record_id, category)
        await self._storage.put(path, blob)
        self._cache.put(path, blob)
        entries = await self._load_index()
        entries.append(
            IndexEntry(
                id=record_id,
                category=category,
                key_version=version,
                created_at=now,
                updated_at=now,
                size=len(blob),
                content_hash=hashlib.sha256(content_bytes).hexdigest(),
                metadata=metadata or {},
            )
        )
        await self._save_index(entries)
        self._audit.log(
            "memory.store", record_id, metadata={"category": category, "size": len(blob)}
        )
        return MemoryRecord(
            id=record_id,
            category=category,
            content=content,
            metadata=metadata or {},
            created_at=now,
            updated_at=now,
        )

    async def retrieve(self, record_id: str) -> MemoryRecord:
        """Download, decrypt and return one record (plaintext transient in RAM)."""
        entry = self._find_entry(await self._load_index(), record_id)
        if entry.deleted_at is not None:
            raise RecordNotFoundError(f"record {record_id} has been deleted")
        content = await self._decrypt_entry(entry)
        if hashlib.sha256(content.encode("utf-8")).hexdigest() != entry.content_hash:
            self._audit.log("memory.retrieve", record_id, status="failed", reason="hash mismatch")
            raise RecordNotFoundError(f"record {record_id} failed integrity verification")
        self._audit.log("memory.retrieve", record_id, metadata={"category": entry.category})
        return MemoryRecord(
            id=entry.id,
            category=entry.category,
            content=content,
            metadata=entry.metadata,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
            deleted_at=entry.deleted_at,
        )

    async def search(
        self, query: str, category: str | None = None, limit: int = 20
    ) -> list[SearchHit]:
        """Keyword search: decrypt-and-filter within the session (Phase 0 scope)."""
        needle = query.strip().lower()
        if not needle:
            return []
        hits: list[SearchHit] = []
        for entry in await self._load_index():
            if entry.deleted_at is not None:
                continue
            if category is not None and entry.category != category:
                continue
            content = await self._decrypt_entry(entry)
            if needle in content.lower():
                score = 1.0
            elif needle in json.dumps(entry.metadata).lower():
                score = 0.5
            else:
                continue
            hits.append(
                SearchHit(
                    id=entry.id,
                    category=entry.category,
                    preview=content[:80],
                    score=score,
                    created_at=entry.created_at,
                )
            )
        hits.sort(key=lambda hit: hit.score, reverse=True)
        self._audit.log(
            "memory.search",
            category or "*",
            metadata={"query_terms": len(needle), "hits": len(hits)},
        )
        return hits[:limit]

    async def delete(self, record_id: str) -> None:
        """Soft-delete a record (blob retained for the grace period)."""
        entries = await self._load_index()
        entry = self._find_entry(entries, record_id)
        entry.deleted_at = _iso_now()
        entry.updated_at = entry.deleted_at
        await self._save_index(entries)
        self._audit.log("memory.delete", record_id, metadata={"category": entry.category})

    async def list_categories(self) -> dict[str, int]:
        """Return non-deleted record counts per category."""
        counts: dict[str, int] = {}
        for entry in await self._load_index():
            if entry.deleted_at is None:
                counts[entry.category] = counts.get(entry.category, 0) + 1
        return counts

    async def count_records(self) -> int:
        """Return the number of live (non-deleted) records."""
        return sum(1 for entry in await self._load_index() if entry.deleted_at is None)
