"""Memory consolidation: merge similar memories, deduplicate, re-score importance.

All similarity work runs over the encrypted metadata index (embeddings live
there, never plaintext), so content is decrypted only for memories that are
actually merged. ``MemoryConsolidator.run`` wraps a full pass with job
tracking: every run is recorded (encrypted) in a history blob so clients can
inspect status and results, past jobs and a ``last_consolidation`` timestamp.
"""

import json
import uuid
from datetime import UTC, datetime

import numpy as np

from mysti.exceptions import RecordNotFoundError
from mysti.memory import envelope
from mysti.memory.service import MemoryService, _clamp_importance
from mysti.security.audit import AuditLog
from mysti.security.keys import KeyManager
from mysti.storage.base import StorageBackend

SIMILARITY_THRESHOLD = 0.85

CONSOLIDATION_HISTORY_KEY = "mysti/metadata/consolidation_history.enc"
CONSOLIDATION_HISTORY_AAD = b"mysti:consolidation-history"


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


class MemoryConsolidator:
    """Merges similar memories, removes duplicates and scores importance."""

    def __init__(
        self,
        memory: MemoryService,
        audit: AuditLog,
        keys: KeyManager | None = None,
        storage: StorageBackend | None = None,
    ) -> None:
        self._memory = memory
        self._audit = audit
        self._keys = keys
        self._storage = storage

    @staticmethod
    def _pairwise_similarity(matrix: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0.0] = 1.0
        normalized = matrix / norms
        return normalized @ normalized.T

    async def deduplicate(self, category: str | None = None) -> int:
        """Remove exact duplicates (same content hash), keeping the first.

        Returns the number of records removed. Duplicates are detected via
        the ``content_hash`` in the index, so no decryption is required.
        """
        seen: set[str] = set()
        removed = 0
        # iterate newest-first so the most recently stored duplicate is kept
        entries = await self._memory.entries(category)
        for entry in reversed(entries):
            if entry.content_hash in seen:
                await self._memory.delete(entry.id)
                removed += 1
            else:
                seen.add(entry.content_hash)
        if removed:
            self._audit.log(
                "memory.deduplicate", category or "*", metadata={"removed": removed}
            )
        return removed

    async def consolidate(self, category: str | None = None) -> dict:
        """Merge similar memories (cosine similarity > 0.85) into single records.

        The merged record keeps the primary (older) record's id and timestamps,
        the union of tags, the max importance, and concatenated content.
        Returns stats: ``merged``, ``removed`` and ``updated`` counts.
        """
        removed = await self.deduplicate(category)
        live = [e for e in await self._memory.entries(category) if e.embedding is not None]
        merged = 0
        if len(live) >= 2:
            matrix = np.asarray([entry.embedding for entry in live], dtype=np.float32)
            similarities = self._pairwise_similarity(matrix)
            merged_ids: set[str] = set()
            for i in range(len(live)):
                if live[i].id in merged_ids:
                    continue
                for j in range(i + 1, len(live)):
                    if live[j].id in merged_ids:
                        continue
                    if similarities[i, j] <= SIMILARITY_THRESHOLD:
                        continue
                    primary, secondary = live[i], live[j]
                    content_a = await self._memory.decrypt_content(primary)
                    content_b = await self._memory.decrypt_content(secondary)
                    if content_a.strip() == content_b.strip():
                        continue
                    combined = content_a.rstrip() + "\n\n" + content_b.strip()
                    updated = await self._memory.update_content(primary.id, combined)
                    await self._memory.update_metadata(
                        primary.id,
                        tags=sorted(set(primary.tags) | set(secondary.tags)),
                        importance=max(primary.importance, secondary.importance),
                        metadata={
                            **primary.metadata,
                            "merged_from": [primary.id, secondary.id],
                            "merged_count": primary.metadata.get("merged_count", 1) + 1,
                        },
                    )
                    await self._memory.delete(secondary.id)
                    # keep the loop's view of the primary record fresh
                    primary.embedding = updated.embedding
                    primary.content_hash = updated.content_hash
                    merged_ids.add(secondary.id)
                    merged += 1
        self._audit.log(
            "memory.consolidate",
            category or "*",
            metadata={"merged": merged, "removed": removed},
        )
        return {"merged": merged, "removed": removed, "updated": merged + removed}

    async def update_importance(self, category: str | None = None) -> int:
        """Re-score importance from access patterns; returns records updated.

        Frequently accessed memories gain importance; memories untouched for
        over 30 days decay. Importance stays within 1-10.
        """
        updated = 0
        for entry in await self._memory.entries(category):
            score = entry.importance
            if entry.access_count >= 5:
                score += 1
            if entry.last_accessed:
                try:
                    last = datetime.fromisoformat(entry.last_accessed)
                except ValueError:
                    last = None
                if last is not None and (datetime.now(UTC) - last).days > 30:
                    score -= 1
            new_score = _clamp_importance(score)
            if new_score != entry.importance:
                await self._memory.update_metadata(entry.id, importance=new_score)
                updated += 1
        self._audit.log(
            "memory.update_importance", category or "*", metadata={"updated": updated}
        )
        return updated

    # ------------------------------------------------------------ job tracking
    async def _load_history(self) -> list[dict]:
        if self._keys is None or self._storage is None:
            return []
        try:
            blob = await self._storage.get(CONSOLIDATION_HISTORY_KEY)
        except RecordNotFoundError:
            return []
        key, _ = await self._keys.get_category_key("meta")
        try:
            data = envelope.decrypt(key, blob, CONSOLIDATION_HISTORY_AAD)
            return json.loads(data)
        except Exception:  # noqa: BLE001 - a corrupt history is not fatal
            return []

    async def _save_history(self, history: list[dict]) -> None:
        if self._keys is None or self._storage is None:
            return
        key, _ = await self._keys.get_category_key("meta")
        payload = json.dumps(history).encode("utf-8")
        await self._storage.put(
            CONSOLIDATION_HISTORY_KEY, envelope.encrypt(key, payload, CONSOLIDATION_HISTORY_AAD)
        )

    async def run(
        self, category: str | None = None, skip_importance: bool = False
    ) -> dict:
        """Execute a full consolidation pass with status and history tracking.

        Runs deduplication, similarity merging and (unless skipped) importance
        re-scoring, records the outcome as a job, and returns the job dict with
        an ``id``, ``status`` (``completed`` / ``failed``) and timings — letting
        callers poll or reason about the run afterwards.
        """
        job: dict = {
            "id": str(uuid.uuid4()),
            "status": "running",
            "category": category,
            "started_at": _iso_now(),
            "completed_at": None,
            "merged": 0,
            "removed": 0,
            "importance_updated": 0,
            "error": None,
        }
        try:
            job["removed"] = await self.deduplicate(category)
            stats = await self.consolidate(category)
            job["merged"] = stats["merged"]
            job["removed"] += stats["removed"]
            if not skip_importance:
                job["importance_updated"] = await self.update_importance(category)
            job["status"] = "completed"
        except Exception as exc:  # noqa: BLE001 - record the failure, re-raise
            job["status"] = "failed"
            job["error"] = str(exc)
            await self._append_job(job)
            raise
        finally:
            job["completed_at"] = _iso_now()
        await self._append_job(job)
        return job

    async def _append_job(self, job: dict) -> None:
        history = await self._load_history()
        history.append(job)
        history = history[-50:]
        await self._save_history(history)
        self._audit.log(
            "memory.consolidate.run",
            job.get("category") or "*",
            metadata={"job_id": job["id"], "status": job["status"]},
        )

    async def history(self, limit: int = 20) -> list[dict]:
        """Return the most recent consolidation jobs, newest first."""
        jobs = await self._load_history()
        jobs.sort(key=lambda job: job.get("started_at", ""), reverse=True)
        return jobs[:limit]

    async def get_job(self, job_id: str) -> dict:
        """Return one consolidation job by id.

        Raises:
            RecordNotFoundError: If the job id is unknown.
        """
        for job in await self._load_history():
            if job["id"] == job_id:
                return job
        raise RecordNotFoundError(f"consolidation job not found: {job_id}")
