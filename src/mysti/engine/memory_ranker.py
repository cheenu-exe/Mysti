"""Memory ranker: scores and ranks memory hits for relevance to a query.

Phase B adds:
- Relevance scoring with configurable weights
- Deduplication of similar memories
- Importance-based boosting
- Time decay for older memories
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol


class SearchHit(Protocol):
    """Minimal search hit interface."""

    @property
    def id(self) -> str: ...
    @property
    def preview(self) -> str: ...
    @property
    def score(self) -> float: ...
    @property
    def category(self) -> str: ...
    @property
    def created_at(self) -> str: ...


@dataclass
class RankedMemory:
    """A memory with computed relevance score and ranking metadata."""

    hit: SearchHit
    relevance_score: float
    rank: int = 0
    reason: str = ""


class MemoryRanker:
    """Ranks memory search hits by relevance to a query.

    Combines:
    - Original search score (semantic/keyword similarity)
    - Importance boost (higher importance = higher rank)
    - Time decay (newer memories ranked higher)
    - Deduplication (similar previews merged)
    """

    def __init__(
        self,
        semantic_weight: float = 0.6,
        importance_weight: float = 0.2,
        time_weight: float = 0.2,
        dedup_threshold: float = 0.9,
    ) -> None:
        self.semantic_weight = semantic_weight
        self.importance_weight = importance_weight
        self.time_weight = time_weight
        self.dedup_threshold = dedup_threshold

    def _compute_time_decay(self, created_at: str, half_life_days: float = 30.0) -> float:
        """Compute time decay score: 1.0 for now, decays by half every half_life_days."""
        try:
            created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            now = datetime.now(UTC)
            age_days = max(0, (now - created).total_seconds() / 86400)
            return 2 ** (-age_days / half_life_days)
        except (ValueError, TypeError):
            return 0.5  # default for unparseable dates

    def _is_duplicate(self, preview_a: str, preview_b: str) -> bool:
        """Check if two previews are near-duplicates.

        Only considers exact matches or very high similarity on longer texts.
        Short previews (< 20 chars) are never considered duplicates.
        """
        a = preview_a.lower().strip()
        b = preview_b.lower().strip()
        if a == b:
            return True
        # Never dedup short previews
        if len(a) < 20 or len(b) < 20:
            return False
        # Jaccard on words for longer texts
        words_a = set(a.split())
        words_b = set(b.split())
        if not words_a or not words_b:
            return False
        intersection = words_a & words_b
        union = words_a | words_b
        similarity = len(intersection) / len(union)
        return similarity >= self.dedup_threshold

    def rank(
        self,
        hits: list[SearchHit],
        *,
        max_results: int = 5,
        boost_importance: bool = True,
        apply_time_decay: bool = True,
    ) -> list[RankedMemory]:
        """Rank search hits by combined relevance score.

        Args:
            hits: Raw search hits from memory service.
            max_results: Maximum results to return.
            boost_importance: Whether to factor in importance scores.
            apply_time_decay: Whether to factor in recency.

        Returns:
            Ranked memories sorted by relevance, deduplicated.
        """
        if not hits:
            return []

        # Deduplicate
        unique_hits: list[SearchHit] = []
        for hit in hits:
            is_dup = False
            for existing in unique_hits:
                if self._is_duplicate(hit.preview, existing.preview):
                    is_dup = True
                    break
            if not is_dup:
                unique_hits.append(hit)

        # Score each hit
        ranked: list[RankedMemory] = []
        for hit in unique_hits:
            # Base score from search
            base_score = hit.score if hasattr(hit, "score") else 0.5

            # Importance boost (importance is 1-10, normalize to 0-1)
            importance = getattr(hit, "importance", 5)
            importance_score = min(1.0, max(0.0, (importance - 1) / 9)) if boost_importance else 0.5

            # Time decay
            time_score = self._compute_time_decay(hit.created_at) if apply_time_decay else 1.0

            # Combined score
            relevance = (
                base_score * self.semantic_weight
                + importance_score * self.importance_weight
                + time_score * self.time_weight
            )

            reason_parts = []
            if base_score > 0.7:
                reason_parts.append("high similarity")
            elif base_score > 0.4:
                reason_parts.append("moderate similarity")
            else:
                reason_parts.append("low similarity")

            if boost_importance and importance >= 7:
                reason_parts.append("high importance")
            if apply_time_decay and time_score > 0.8:
                reason_parts.append("recent")

            ranked.append(RankedMemory(
                hit=hit,
                relevance_score=round(relevance, 6),
                reason=", ".join(reason_parts) if reason_parts else "matched",
            ))

        # Sort by relevance descending
        ranked.sort(key=lambda r: r.relevance_score, reverse=True)

        # Assign ranks
        for i, mem in enumerate(ranked):
            mem.rank = i + 1

        return ranked[:max_results]
