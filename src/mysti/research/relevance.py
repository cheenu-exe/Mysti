"""Relevance engine: scores, filters, deduplicates and ranks research items.

Scoring rubric (0-10):
  - keyword match: 0-4  (title hits weigh double, category match = 1 point)
  - source quality: 0-2 (arxiv > github > hackernews > rss)
  - recency:        0-2 (exponential decay over ~30 days)
  - author:         0-2 (known-author list from the interest profile)

The user interest profile lives at ``~/.config/mysti/interests.json``.
"""

import json
import math
from datetime import UTC, datetime
from pathlib import Path

from mysti.research.models import ResearchItem

SOURCE_QUALITY: dict[str, float] = {
    "arxiv": 2.0,
    "github": 1.5,
    "hackernews": 1.0,
    "rss": 0.5,
}

DEFAULT_PROFILE: dict = {
    "keywords": ["cybersecurity", "CTF", "machine learning", "DevSecOps"],
    "categories": ["cs.CR", "cs.AI", "cs.SE"],
    "importance_threshold": 5,
}


def default_interests_path() -> Path:
    return Path.home() / ".config" / "mysti" / "interests.json"


def load_profile(path: Path | None = None) -> dict:
    """Load the interest profile, falling back to defaults.

    Supported keys: ``keywords`` (strings, optionally ``"term@weight"``),
    ``weights`` (term -> float multiplier, overrides ``@weight`` suffixes),
    ``topics`` (list of ``{"name", "keywords"}`` dicts whose terms score with
    a 1.5x boost, modelling broader areas of interest), ``projects`` (active
    project names, scored 1.5x like keywords), ``categories``, ``trusted_authors``,
    ``importance_threshold`` and ``dismissed`` (URLs the user marked irrelevant).
    """
    path = path or default_interests_path()
    if not path.exists():
        return json.loads(json.dumps(DEFAULT_PROFILE))
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return json.loads(json.dumps(DEFAULT_PROFILE))
    profile = json.loads(json.dumps(DEFAULT_PROFILE))
    for key in ("keywords", "categories", "projects", "trusted_authors", "dismissed"):
        if isinstance(data.get(key), list):
            profile[key] = [str(k) for k in data[key]]
    if isinstance(data.get("importance_threshold"), (int, float)):
        profile["importance_threshold"] = float(data["importance_threshold"])
    if isinstance(data.get("weights"), dict):
        profile["weights"] = {str(k): float(v) for k, v in data["weights"].items()}
    if isinstance(data.get("topics"), list):
        topics = []
        for topic in data["topics"]:
            if isinstance(topic, dict):
                topics.append(
                    {
                        "name": str(topic.get("name", "")),
                        "keywords": [str(k) for k in topic.get("keywords", [])],
                    }
                )
        profile["topics"] = topics
    return profile


def save_profile(profile: dict, path: Path | None = None) -> None:
    """Persist an interest profile to ``path`` (default config location)."""
    path = path or default_interests_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, indent=2), encoding="utf-8")


def _keyword_terms(profile: dict) -> list[tuple[str, float]]:
    """Flatten keywords/topics/projects into ``(term, weight)`` pairs.

    Each bare keyword weighs 1.0; ``"term@weight"`` and the ``weights`` map
    override it; topics and projects score with a 1.5x boost since they model
    broader, ongoing interests.
    """
    weights = {str(k): float(v) for k, v in profile.get("weights", {}).items()}
    pairs: dict[str, float] = {}
    for raw in profile.get("keywords", []):
        term, _, suffix = str(raw).partition("@")
        pairs[term.lower()] = float(suffix) if suffix else weights.get(term.lower(), 1.0)
    for topic in profile.get("topics", []):
        for raw in topic.get("keywords", []):
            term, _, suffix = str(raw).partition("@")
            weight = (float(suffix) if suffix else weights.get(term.lower(), 1.0)) * 1.5
            pairs[term.lower()] = max(pairs.get(term.lower(), 0.0), weight)
    for project in profile.get("projects", []):
        term = str(project).lower()
        pairs[term] = max(pairs.get(term, 0.0), 1.5)
    return list(pairs.items())


class RelevanceEngine:
    """Scores research items against a user interest profile."""

    def __init__(self, profile: dict | None = None, profile_path: Path | None = None) -> None:
        self.profile = profile or load_profile(profile_path)
        self.profile_path = profile_path

    # ------------------------------------------------------------------ score
    async def score(self, item: ResearchItem) -> float:
        """Return a 0-10 relevance score for ``item``.

        Items whose URL is in the profile's ``dismissed`` list (explicit user
        feedback) score 0 immediately and are never surfaced again.
        """
        if item.url and item.url.strip().lower() in {
            str(u).lower() for u in self.profile.get("dismissed", [])
        }:
            return 0.0
        return (
            self._keyword_score(item)
            + self._source_score(item)
            + self._recency_score(item)
            + self._author_score(item)
        )

    def _keyword_score(self, item: ResearchItem) -> float:
        """0-4 points; title matches weigh more than body matches."""
        terms = _keyword_terms(self.profile)
        if not terms:
            return 0.0
        title = item.title.lower()
        text = f"{title} {item.content.lower()}"
        cats = {c.lower() for c in item.metadata.get("categories", [])}
        wanted_cats = {c.lower() for c in self.profile.get("categories", [])}

        points = 0.0
        for term, weight in terms:
            if term in title:
                points += 1.0 * weight
            elif term in text:
                points += 0.5 * weight
        if wanted_cats & cats:
            points += 1.0
        return min(4.0, points)

    def _source_score(self, item: ResearchItem) -> float:
        """0-2 points based on source quality ranking."""
        return SOURCE_QUALITY.get(item.source, 0.5)

    def _recency_score(self, item: ResearchItem) -> float:
        """0-2 points; exponential decay with a ~30 day half-life."""
        if not item.published_at:
            return 0.5
        try:
            published = datetime.fromisoformat(item.published_at.replace("Z", "+00:00"))
        except ValueError:
            return 0.5
        if published.tzinfo is None:
            published = published.replace(tzinfo=UTC)
        age_days = max(0.0, (datetime.now(UTC) - published).total_seconds() / 86400)
        if age_days <= 1.0:
            return 2.0  # no decay within the first day
        return 2.0 * math.exp(-(age_days - 1.0) / 30.0)

    def _author_score(self, item: ResearchItem) -> float:
        """0-2 points for known/trusted authors."""
        trusted = {a.lower() for a in self.profile.get("trusted_authors", [])}
        if not item.author:
            return 0.0
        return 2.0 if item.author.lower() in trusted else 0.0

    # ----------------------------------------------------------------- filter
    async def filter(
        self, items: list[ResearchItem], min_score: float = 5.0
    ) -> list[ResearchItem]:
        """Drop items below ``min_score`` or with empty/placeholder titles."""
        kept: list[ResearchItem] = []
        for item in items:
            if not item.title or item.title == "(untitled)":
                continue
            if await self.score(item) >= min_score:
                kept.append(item)
        return kept

    # ------------------------------------------------------------ deduplicate
    async def deduplicate(self, items: list[ResearchItem]) -> list[ResearchItem]:
        """Remove cross-source duplicates by URL/title fingerprint.

        Keeps the first occurrence (callers pass source-priority or ranked
        order); identical URLs across sources collapse to a single item.
        """
        seen: set[str] = set()
        unique: list[ResearchItem] = []
        for item in items:
            fp = item.fingerprint()
            if fp in seen:
                continue
            seen.add(fp)
            unique.append(item)
        return unique

    # ------------------------------------------------------------------- rank
    async def rank(self, items: list[ResearchItem]) -> list[ResearchItem]:
        """Return items sorted by relevance score, highest first."""
        scored = [(await self.score(item), item) for item in items]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [item for _, item in scored]

    async def score_all(self, items: list[ResearchItem]) -> list[tuple[float, ResearchItem]]:
        """Return (score, item) pairs sorted by score descending."""
        scored = [(await self.score(item), item) for item in items]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return scored

    # ---------------------------------------------------------------- feedback
    async def record_feedback(self, item: ResearchItem, relevant: bool) -> None:
        """Record explicit user feedback to adapt future ranking.

        ``relevant=False`` adds the item URL to ``dismissed`` (it then always
        scores 0); ``relevant=True`` promotes the item's author to
        ``trusted_authors`` so their future work ranks higher. Persists to the
        profile file when one was configured at construction time.
        """
        if relevant:
            authors = [str(a) for a in self.profile.get("trusted_authors", [])]
            if item.author and item.author not in authors:
                authors.append(item.author)
                self.profile["trusted_authors"] = authors
        elif item.url:
            dismissed = [str(u) for u in self.profile.get("dismissed", [])]
            normalized = item.url.strip().lower()
            if normalized not in {d.lower() for d in dismissed}:
                dismissed.append(normalized)
                self.profile["dismissed"] = dismissed
        if self.profile_path is not None:
            save_profile(self.profile, self.profile_path)
        return None
