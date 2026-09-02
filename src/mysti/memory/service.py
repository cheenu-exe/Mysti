"""Memory service: the only layer where plaintext records exist (transiently).

Structured storage with semantic search (Phase 1). Content is sealed with the
category key before upload; the per-category metadata index is encrypted with
the reserved ``meta`` category key and holds no plaintext content — only ids,
timestamps, tags, importance, access statistics and the embedding vectors used
for semantic ranking. An in-RAM search index (record id -> embedding/metadata)
is loaded from the encrypted index on first use and updated incrementally on
every store/delete, so filtering and ranking never decrypt a record that does
not match.
"""

import hashlib
import json
import re
import uuid
from datetime import UTC, datetime

from mysti.exceptions import RecordNotFoundError, ValidationError
from mysti.memory import envelope
from mysti.memory.cache import BlobCache
from mysti.memory.embeddings import EmbeddingService, cosine_similarity
from mysti.memory.models import IndexEntry, MemoryRecord, SearchHit
from mysti.security.audit import AuditLog
from mysti.security.keys import KeyManager
from mysti.storage.base import StorageBackend

INDEX_KEY = "mysti/memories/index.enc"
INDEX_AAD = b"mysti:memory-index"
MAX_IMPORTANCE = 10
MIN_IMPORTANCE = 1


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


def _clamp_importance(value: int) -> int:
    return max(MIN_IMPORTANCE, min(MAX_IMPORTANCE, int(value)))


def _match_type(semantic: float, keyword: float) -> str:
    """Classify how a search hit matched: semantic, keyword or hybrid."""
    if semantic > 0.0 and keyword > 0.0:
        return "hybrid"
    if semantic > 0.0:
        return "semantic"
    return "keyword"


def _search_explanation(semantic: float, keyword: float) -> str:
    """Human-readable reason a search hit ranked."""
    if semantic > 0.0 and keyword > 0.0:
        return "matched both by meaning and by exact wording"
    if semantic > 0.0:
        return f"semantically similar (cosine {semantic:.3f})"
    return "contains the exact search wording"


def record_path(record_id: str, category: str) -> str:
    """Remote storage path for a memory record blob."""
    return f"mysti/memories/{category}/{record_id}.enc"


class MemoryService:
    """Encrypted personal memory storage with semantic search and metadata."""

    def __init__(
        self,
        storage: StorageBackend,
        keys: KeyManager,
        cache: BlobCache,
        audit: AuditLog,
        embeddings: EmbeddingService | None = None,
        max_record_bytes: int = 1024 * 1024,
    ) -> None:
        self._storage = storage
        self._keys = keys
        self._cache = cache
        self._audit = audit
        self._embeddings = embeddings
        self._max_record_bytes = max_record_bytes
        self._search_index: dict[str, dict] | None = None

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

    async def _rebuild_search_index(self) -> dict[str, dict]:
        index: dict[str, dict] = {}
        for entry in await self._load_index():
            if entry.deleted_at is None:
                index[entry.id] = {
                    "category": entry.category,
                    "embedding": entry.embedding,
                    "importance": entry.importance,
                    "tags": entry.tags,
                    "created_at": entry.created_at,
                }
        return index

    async def _ensure_search_index(self) -> dict[str, dict]:
        """In-RAM search index, loaded once and updated incrementally."""
        if self._search_index is None:
            self._search_index = await self._rebuild_search_index()
        return self._search_index

    async def _embed_content(self, content: str) -> list[float] | None:
        if self._embeddings is None:
            return None
        vector = await self._embeddings.generate_embedding(content)
        return vector or None

    # --- public API ---

    async def store(
        self,
        category: str,
        content: str,
        metadata: dict | None = None,
        *,
        tags: list[str] | None = None,
        source: str = "chat",
        importance: int = 5,
    ) -> MemoryRecord:
        """Encrypt ``content`` locally and upload it; returns the new record.

        Structured fields (tags, source, importance) and the content embedding
        are stored in the encrypted metadata index, separate from the sealed
        content blob, so they can be filtered without decryption.
        """
        known = await self._keys.category_names()
        if category not in known or category in ("meta", "conversation"):
            raise ValidationError(f"unknown memory category: {category!r}")
        if not content.strip():
            raise ValidationError("memory content must not be empty")
        importance = _clamp_importance(importance)
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
        embedding = await self._embed_content(content)
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
                tags=list(tags or []),
                source=source,
                importance=importance,
                last_accessed=now,
                embedding=embedding,
                metadata=metadata or {},
            )
        )
        await self._save_index(entries)
        if self._search_index is not None:
            self._search_index[record_id] = {
                "category": category,
                "embedding": embedding,
                "importance": importance,
                "tags": list(tags or []),
                "created_at": now,
            }
        self._audit.log(
            "memory.store",
            record_id,
            metadata={"category": category, "size": len(blob), "embedded": embedding is not None},
        )
        return MemoryRecord(
            id=record_id,
            category=category,
            content=content,
            content_hash=hashlib.sha256(content_bytes).hexdigest(),
            tags=list(tags or []),
            source=source,
            importance=importance,
            metadata=metadata or {},
            created_at=now,
            updated_at=now,
            last_accessed=now,
            embedding=embedding,
        )

    async def retrieve(self, record_id: str) -> MemoryRecord:
        """Download, decrypt and return one record (plaintext transient in RAM).

        Updates the access statistics (``access_count`` / ``last_accessed``)
        used by consolidation to score importance.
        """
        entries = await self._load_index()
        entry = self._find_entry(entries, record_id)
        if entry.deleted_at is not None:
            raise RecordNotFoundError(f"record {record_id} has been deleted")
        content = await self._decrypt_entry(entry)
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if content_hash != entry.content_hash:
            self._audit.log("memory.retrieve", record_id, status="failed", reason="hash mismatch")
            raise RecordNotFoundError(f"record {record_id} failed integrity verification")
        now = _iso_now()
        entry.access_count += 1
        entry.last_accessed = now
        await self._save_index(entries)
        if self._search_index is not None and record_id in self._search_index:
            self._search_index[record_id]["importance"] = entry.importance
        self._audit.log("memory.retrieve", record_id, metadata={"category": entry.category})
        return MemoryRecord(
            id=entry.id,
            category=entry.category,
            content=content,
            content_hash=content_hash,
            tags=entry.tags,
            source=entry.source,
            importance=entry.importance,
            metadata=entry.metadata,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
            last_accessed=entry.last_accessed,
            access_count=entry.access_count,
            embedding=entry.embedding,
            deleted_at=entry.deleted_at,
        )

    async def search(
        self,
        query: str,
        category: str | None = None,
        limit: int = 20,
        *,
        semantic_weight: float = 1.0,
        keyword_weight: float = 1.0,
    ) -> list[SearchHit]:
        """Hybrid semantic + keyword search.

        Each candidate scores ``semantic * semantic_weight + keyword *
        keyword_weight`` where ``semantic`` is the cosine similarity between the
        query embedding and the stored embedding and ``keyword`` is 1.0 for an
        exact substring match in the content (0.5 for a match inside metadata).
        The final score is clamped to [0, 1]. Every hit records its ``match_type``
        (``semantic`` / ``keyword`` / ``hybrid``) and a short explanation. Content
        is decrypted only for records that match, and only to build the preview.

        Args:
            query: Free-text search query.
            category: Restrict results to one category when given.
            limit: Maximum number of results to return.
            semantic_weight: Weight applied to vector similarity.
            keyword_weight: Weight applied to exact keyword matches.
        """
        needle = query.strip().lower()
        if not needle:
            return []
        await self._ensure_search_index()
        query_embedding: list[float] | None = None
        if self._embeddings is not None:
            query_embedding = await self._embeddings.generate_embedding(needle) or None
        hits: list[SearchHit] = []
        for entry in await self._load_index():
            if entry.deleted_at is not None:
                continue
            if category is not None and entry.category != category:
                continue
            content = await self._decrypt_entry(entry)
            semantic = 0.0
            if query_embedding is not None and entry.embedding is not None:
                semantic = max(0.0, cosine_similarity(query_embedding, entry.embedding))
            if needle in content.lower():
                keyword = 1.0
            elif needle in json.dumps(entry.metadata).lower():
                keyword = 0.5
            else:
                keyword = 0.0
            score = semantic * max(0.0, semantic_weight) + keyword * max(0.0, keyword_weight)
            if score <= 0.0:
                continue
            hit = SearchHit(
                id=entry.id,
                category=entry.category,
                preview=content[:80],
                score=round(min(score, 1.0), 6),
                created_at=entry.created_at,
                match_type=_match_type(semantic, keyword),
                explanation=_search_explanation(semantic, keyword),
            )
            hits.append(hit)
        hits.sort(key=lambda hit: (hit.score, hit.created_at), reverse=True)
        self._audit.log(
            "memory.search",
            category or "*",
            metadata={
                "hits": len(hits),
                "semantic": query_embedding is not None,
                "semantic_weight": semantic_weight,
                "keyword_weight": keyword_weight,
            },
        )
        return hits[:limit]

    async def suggest(
        self, query: str, category: str | None = None, limit: int = 8
    ) -> list[str]:
        """Return up to ``limit`` stored-memory terms completing ``query``.

        Used by the search-suggestion endpoint for autocomplete. Terms come
        from tags (weighted higher) and the vocabulary of stored content, so
        suggestions always reflect what the user actually saved.
        """
        prefix = query.strip().lower()
        counts: dict[str, int] = {}
        for entry in await self._load_index():
            if entry.deleted_at is not None:
                continue
            if category is not None and entry.category != category:
                continue
            for tag in entry.tags:
                lowered = tag.lower()
                counts[lowered] = counts.get(lowered, 0) + 3
            try:
                content = (await self._decrypt_entry(entry)).lower()
            except Exception:  # noqa: BLE001 - skip unreadable records
                continue
            for token in re.findall(r"[a-z0-9][a-z0-9_\-]{2,}", content):
                counts[token] = counts.get(token, 0) + 1
        ordered = [
            term for term, _ in sorted(counts.items(), key=lambda pair: pair[1], reverse=True)
        ]
        if prefix:
            ordered = [term for term in ordered if term.startswith(prefix)]
        return ordered[:limit]

    async def delete(self, record_id: str) -> None:
        """Soft-delete a record (blob retained for the grace period)."""
        entries = await self._load_index()
        entry = self._find_entry(entries, record_id)
        entry.deleted_at = _iso_now()
        entry.updated_at = entry.deleted_at
        await self._save_index(entries)
        if self._search_index is not None:
            self._search_index.pop(record_id, None)
        self._audit.log("memory.delete", record_id, metadata={"category": entry.category})

    # --- structured storage helpers (used by categories / consolidation) ---

    async def entries(
        self, category: str | None = None, include_deleted: bool = False
    ) -> list[IndexEntry]:
        """Return index entries, optionally filtered by category."""
        result: list[IndexEntry] = []
        for entry in await self._load_index():
            if entry.deleted_at is not None and not include_deleted:
                continue
            if category is not None and entry.category != category:
                continue
            result.append(entry)
        return result

    async def get_entry(self, record_id: str) -> IndexEntry:
        """Return one index entry (no decryption of content)."""
        return self._find_entry(await self._load_index(), record_id)

    async def decrypt_content(self, entry: IndexEntry) -> str:
        """Public wrapper: decrypt the content blob for one index entry."""
        return await self._decrypt_entry(entry)

    async def update_metadata(
        self,
        record_id: str,
        *,
        tags: list[str] | None = None,
        importance: int | None = None,
        metadata: dict | None = None,
    ) -> IndexEntry:
        """Update structured metadata without touching the encrypted content."""
        entries = await self._load_index()
        entry = self._find_entry(entries, record_id)
        if entry.deleted_at is not None:
            raise RecordNotFoundError(f"record {record_id} has been deleted")
        if tags is not None:
            entry.tags = list(tags)
        if importance is not None:
            entry.importance = _clamp_importance(importance)
        if metadata is not None:
            entry.metadata = metadata
        entry.updated_at = _iso_now()
        await self._save_index(entries)
        if self._search_index is not None and record_id in self._search_index:
            self._search_index[record_id]["importance"] = entry.importance
            self._search_index[record_id]["tags"] = entry.tags
        self._audit.log("memory.update_metadata", record_id, metadata={"category": entry.category})
        return entry

    async def update_content(self, record_id: str, content: str) -> MemoryRecord:
        """Replace the content of a record (re-seals with its current key version)."""
        if not content.strip():
            raise ValidationError("memory content must not be empty")
        content_bytes = content.encode("utf-8")
        if len(content_bytes) > self._max_record_bytes:
            raise ValidationError(f"record exceeds maximum size of {self._max_record_bytes} bytes")
        entries = await self._load_index()
        entry = self._find_entry(entries, record_id)
        if entry.deleted_at is not None:
            raise RecordNotFoundError(f"record {record_id} has been deleted")
        key, _ = await self._keys.get_category_key(entry.category, entry.key_version)
        blob = envelope.seal(
            key, entry.key_version, envelope.record_aad(entry.id, entry.category), content_bytes
        )
        path = record_path(entry.id, entry.category)
        await self._storage.put(path, blob)
        self._cache.put(path, blob)
        entry.size = len(blob)
        entry.content_hash = hashlib.sha256(content_bytes).hexdigest()
        entry.embedding = await self._embed_content(content)
        entry.updated_at = _iso_now()
        await self._save_index(entries)
        if self._search_index is not None and record_id in self._search_index:
            self._search_index[record_id]["embedding"] = entry.embedding
        self._audit.log("memory.update_content", record_id, metadata={"category": entry.category})
        return await self.retrieve(record_id)

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

    async def stats(self) -> dict:
        """Aggregate statistics: counts, sizes and importance per category.

        Returns totals as well as per-category buckets with ``count``, ``bytes``
        (sum of encrypted blob sizes), ``avg_importance`` and the ``oldest`` /
        ``newest`` record creation timestamps.
        """
        categories: dict[str, dict] = {}
        total = 0
        total_bytes = 0
        all_timestamps: list[str] = []
        for entry in await self._load_index():
            if entry.deleted_at is not None:
                continue
            bucket = categories.setdefault(
                entry.category, {"count": 0, "bytes": 0, "importance": 0}
            )
            if "oldest" not in bucket or entry.created_at < bucket["oldest"]:
                bucket["oldest"] = entry.created_at
            if "newest" not in bucket or entry.created_at > bucket["newest"]:
                bucket["newest"] = entry.created_at
            bucket["count"] += 1
            bucket["bytes"] += entry.size
            bucket["importance"] += entry.importance
            total += 1
            total_bytes += entry.size
            all_timestamps.append(entry.created_at)
        for bucket in categories.values():
            bucket["avg_importance"] = (
                round(bucket.pop("importance") / bucket["count"], 2) if bucket["count"] else 0
            )
        return {
            "total_records": total,
            "total_size_bytes": total_bytes,
            "avg_record_size": round(total_bytes / total, 2) if total else 0,
            "oldest_record": min(all_timestamps) if all_timestamps else None,
            "newest_record": max(all_timestamps) if all_timestamps else None,
            "categories": categories,
        }
