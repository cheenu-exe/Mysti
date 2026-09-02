"""Source connectors: GitHub, arXiv, RSS/Atom and Hacker News.

Every connector is rate-limited (a minimum interval between HTTP requests),
caches parsed results in RAM for an hour, and degrades gracefully: network
and parsing failures yield an empty result set, never an exception to the
caller. All HTTP goes through an injected ``httpx.AsyncClient`` so tests can
substitute a ``MockTransport``.
"""

import asyncio
import logging
import re
import time
import uuid
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from mysti.exceptions import MystiError
from mysti.research.models import ResearchItem

CACHE_TTL_SECONDS = 3600.0
USER_AGENT = "mysti-research/0.1"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
ARXIV_NS = {"arxiv": "http://arxiv.org/schemas/atom"}

logger = logging.getLogger(__name__)


class ConnectorError(MystiError):
    """Raised when a source connector cannot complete a request."""


class SourceConnector(ABC):
    """Base class for research source connectors."""

    name: str = "source"

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        *,
        cache_ttl: float = CACHE_TTL_SECONDS,
        min_interval: float = 1.0,
    ) -> None:
        self._client = client or httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT}, timeout=30.0, follow_redirects=True
        )
        self._owns_client = client is None
        self._cache_ttl = cache_ttl
        self._min_interval = min_interval
        self._cache: dict[str, tuple[float, list[ResearchItem]]] = {}
        self._last_request_at = 0.0
        self._lock = asyncio.Lock()

    async def _rate_limit(self) -> None:
        """Sleep until the minimum interval between requests has elapsed."""
        async with self._lock:
            elapsed = time.monotonic() - self._last_request_at
            if elapsed < self._min_interval:
                await asyncio.sleep(self._min_interval - elapsed)
            self._last_request_at = time.monotonic()

    async def _get_json(self, url: str, params: dict | None = None) -> Any:
        await self._rate_limit()
        response = await self._client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    async def _get_text(self, url: str, params: dict | None = None) -> str:
        await self._rate_limit()
        response = await self._client.get(url, params=params)
        response.raise_for_status()
        return response.text

    def _cache_get(self, key: str) -> list[ResearchItem] | None:
        entry = self._cache.get(key)
        if entry is None:
            return None
        stored_at, items = entry
        if time.monotonic() - stored_at > self._cache_ttl:
            self._cache.pop(key, None)
            return None
        return items

    def _cache_put(self, key: str, items: list[ResearchItem]) -> None:
        self._cache[key] = (time.monotonic(), items)

    @abstractmethod
    async def _fetch(self, query: str | None) -> list[ResearchItem]:
        """Perform the actual source-specific fetch (uncached)."""

    async def fetch(self, query: str | None = None) -> list[ResearchItem]:
        """Fetch items, serving from the one-hour cache when possible.

        Network and parsing errors are swallowed and logged; an empty list is
        returned so one broken source never breaks a briefing.
        """
        key = query or ""
        cached = self._cache_get(key)
        if cached is not None:
            return cached
        try:
            items = await self._fetch(query)
        except (httpx.HTTPError, ConnectorError, ET.ParseError, KeyError, ValueError) as exc:
            logger.warning("connector %r fetch failed for %r: %s", self.name, query, exc)
            return []
        self._cache_put(key, items)
        return items

    async def health_check(self) -> bool:
        """Return True if the source responds successfully right now."""
        try:
            await self._rate_limit()
            response = await self._client.get(self._health_url())
            return response.status_code < 500
        except httpx.HTTPError:
            return False

    @abstractmethod
    def _health_url(self) -> str:
        """Cheap endpoint used by health_check()."""

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    @staticmethod
    def _item(
        source: str,
        title: str,
        content: str,
        *,
        url: str | None = None,
        author: str | None = None,
        published_at: str | None = None,
        **metadata,
    ) -> ResearchItem:
        return ResearchItem(
            id=str(uuid.uuid4()),
            source=source,
            title=title.strip(),
            content=content.strip(),
            url=url,
            author=author,
            published_at=published_at,
            fetched_at=datetime.now(UTC).isoformat(),
            metadata=metadata,
        )


def parse_timestamp(value: str | None) -> str | None:
    """Normalize a timestamp (ISO-8601 or RFC 2822) into ISO-8601 UTC."""
    if not value:
        return None
    text = value.strip()
    parsed = None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        # RFC 2822 style (e.g. "Mon, 31 Aug 2026 08:00:00 GMT" from RSS).
        try:
            from email.utils import parsedate_to_datetime

            parsed = parsedate_to_datetime(text)
        except (TypeError, ValueError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat()


def default_feeds_path() -> Path:
    return Path.home() / ".config" / "mysti" / "feeds.txt"


def load_feeds(path: Path | None = None) -> list[str]:
    """Read configured RSS/Atom feed URLs (one per line, '#' comments)."""
    path = path or default_feeds_path()
    if not path.exists():
        return []
    feeds = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            feeds.append(line)
    return feeds


class GitHubConnector(SourceConnector):
    """GitHub API connector: trending repos, code search and user activity.

    Uses the public REST API v3; unauthenticated requests are limited to
    60/hour by GitHub, hence the aggressive caching and rate limiting.
    """

    name = "github"

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        *,
        token: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(client, **kwargs)
        self._headers = {"Accept": "application/vnd.github+json"}
        if token:
            self._headers["Authorization"] = f"Bearer {token}"

    def _health_url(self) -> str:
        return "https://api.github.com/rate_limit"

    async def fetch_trending(self, since_days: int = 7, limit: int = 15) -> list[ResearchItem]:
        """Recently created repos with the most stars (trending proxy)."""
        cache_key = f"trending:{since_days}:{limit}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        since = datetime.now(UTC) - timedelta(days=since_days)
        data = await self._get_json(
            "https://api.github.com/search/repositories",
            params={
                "q": f"created:>={since:%Y-%m-%d}",
                "sort": "stars",
                "order": "desc",
                "per_page": limit,
            },
        )
        items = [
            self._item(
                self.name,
                repo["full_name"],
                repo.get("description") or "",
                url=repo.get("html_url"),
                author=(repo.get("owner") or {}).get("login"),
                published_at=parse_timestamp(repo.get("created_at")),
                stars=repo.get("stargazers_count", 0),
                language=repo.get("language"),
                kind="trending",
            )
            for repo in data.get("items", [])
        ]
        self._cache_put(cache_key, items)
        return items

    async def search_code(self, query: str, limit: int = 15) -> list[ResearchItem]:
        """Search code across GitHub (requires auth upstream for >10/min)."""
        data = await self._get_json(
            "https://api.github.com/search/code",
            params={"q": query, "per_page": limit},
        )
        return [
            self._item(
                self.name,
                entry["name"],
                entry.get("path") or "",
                url=entry.get("html_url"),
                author=entry.get("repository", {}).get("full_name"),
                kind="code",
            )
            for entry in data.get("items", [])
        ]

    async def fetch_user_activity(self, username: str, limit: int = 30) -> list[ResearchItem]:
        """Recent public events for a user."""
        events = await self._get_json(
            f"https://api.github.com/users/{username}/events/public",
            params={"per_page": min(limit, 90)},
        )
        return [
            self._item(
                self.name,
                f"{event.get('type', 'Event')} in {event.get('repo', {}).get('name', '?')}",
                event.get("payload", {}).get("description") or "",
                url=f"https://github.com/{event.get('repo', {}).get('name', '')}",
                author=username,
                published_at=parse_timestamp(event.get("created_at")),
                kind="activity",
            )
            for event in events
        ]

    async def _fetch(self, query: str | None) -> list[ResearchItem]:
        if query:
            data = await self._get_json(
                "https://api.github.com/search/repositories",
                params={"q": query, "sort": "updated", "per_page": 15},
            )
            return [
                self._item(
                    self.name,
                    repo["full_name"],
                    repo.get("description") or "",
                    url=repo.get("html_url"),
                    author=(repo.get("owner") or {}).get("login"),
                    published_at=parse_timestamp(repo.get("created_at")),
                    stars=repo.get("stargazers_count", 0),
                )
                for repo in data.get("items", [])
            ]
        return await self.fetch_trending()


class ArxivConnector(SourceConnector):
    """arXiv connector: searches papers and fetches abstracts/metadata.

    Supports arXiv category filters (cs.AI, cs.CR, cs.SE, ...). The arXiv
    Atom API asks clients to wait ~3 seconds between requests.
    """

    name = "arxiv"

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        *,
        categories: list[str] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(client, **kwargs)
        self.categories = categories or []
        self._min_interval = max(self._min_interval, 3.0)

    def _health_url(self) -> str:
        return "https://arxiv.org/api/query?search_query=all:test&max_results=1"

    async def search(
        self, topic: str, categories: list[str] | None = None, limit: int = 15
    ) -> list[ResearchItem]:
        """Search arXiv for ``topic``, optionally within categories."""
        cats = categories if categories is not None else self.categories
        query = topic
        if cats:
            query = f"({' OR '.join(f'cat:{c}' for c in cats)}) AND ({topic})"
        return await self.fetch(query)

    async def _fetch(self, query: str | None) -> list[ResearchItem]:
        params: dict[str, Any] = {"start": 0, "max_results": 15}
        if query:
            params["search_query"] = f"all:{query}"
        else:
            params["sortBy"] = "submittedDate"
            params["sortOrder"] = "descending"
        text = await self._get_text("https://arxiv.org/api/query", params=params)
        root = ET.fromstring(text)
        items: list[ResearchItem] = []
        for entry in root.findall("atom:entry", ATOM_NS):
            entry_id = (entry.findtext("atom:id", "", ATOM_NS) or "").strip()
            published = parse_timestamp(entry.findtext("atom:published", None, ATOM_NS))
            authors = [
                (a.findtext("atom:name", "", ATOM_NS) or "").strip()
                for a in entry.findall("atom:author", ATOM_NS)
            ]
            primary_el = entry.find("arxiv:primary_category", ARXIV_NS)
            primary = primary_el.get("term") if primary_el is not None else None
            cats = [c.get("term") for c in entry.findall("atom:category", ATOM_NS) if c.get("term")]
            items.append(
                self._item(
                    self.name,
                    entry.findtext("atom:title", "", ATOM_NS) or "(untitled)",
                    entry.findtext("atom:summary", "", ATOM_NS) or "",
                    url=entry_id or None,
                    author=authors[0] if authors else None,
                    published_at=published,
                    authors=authors,
                    categories=cats,
                    primary_category=primary,
                )
            )
        return items


class RSSConnector(SourceConnector):
    """Generic RSS 2.0 / Atom feed connector with configurable feed URLs.

    Feed URLs are read from ``~/.config/mysti/feeds.txt`` (one per line,
    ``#`` comments allowed) or passed explicitly via ``feeds=[...]``.
    """

    name = "rss"

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        *,
        feeds: list[str] | None = None,
        feeds_path=None,
        **kwargs,
    ) -> None:
        super().__init__(client, **kwargs)
        self._feeds = feeds
        self._feeds_path = feeds_path

    def _resolve_feeds(self) -> list[str]:
        if self._feeds is not None:
            return self._feeds
        return load_feeds(self._feeds_path)

    def _health_url(self) -> str:
        feeds = self._resolve_feeds()
        return feeds[0] if feeds else "https://example.com/feed.xml"

    async def _fetch(self, query: str | None) -> list[ResearchItem]:
        items: list[ResearchItem] = []
        for feed_url in self._resolve_feeds():
            try:
                text = await self._get_text(feed_url)
                items.extend(self._parse_feed(text, feed_url))
            except (httpx.HTTPError, ET.ParseError) as exc:
                logger.warning("rss feed %s failed: %s", feed_url, exc)
        if query:
            needle = query.lower()
            items = [
                item
                for item in items
                if needle in item.title.lower() or needle in item.content.lower()
            ]
        return items

    @staticmethod
    def _strip_html(text: str) -> str:
        return re.sub(r"<[^>]+>", " ", text or "").replace("&amp;", "&").strip()

    def _parse_feed(self, text: str, feed_url: str) -> list[ResearchItem]:
        root = ET.fromstring(text)
        items: list[ResearchItem] = []
        # Atom entries
        for entry in root.findall("atom:entry", ATOM_NS):
            link = ""
            for link_el in entry.findall("atom:link", ATOM_NS):
                link = link_el.get("href") or link
            content_el = entry.find("atom:content", ATOM_NS)
            summary_el = entry.find("atom:summary", ATOM_NS)
            # Body may contain nested (X)HTML; itertext() captures all of it.
            if content_el is not None:
                body = "".join(content_el.itertext())
            elif summary_el is not None:
                body = "".join(summary_el.itertext())
            else:
                body = ""
            items.append(
                self._item(
                    self.name,
                    entry.findtext("atom:title", "", ATOM_NS) or "(untitled)",
                    self._strip_html(body),
                    url=link or feed_url,
                    author=entry.findtext("atom:author/atom:name", None, ATOM_NS),
                    published_at=parse_timestamp(
                        entry.findtext("atom:updated", None, ATOM_NS)
                        or entry.findtext("atom:published", None, ATOM_NS)
                    ),
                    feed=feed_url,
                )
            )
        # RSS 2.0 items
        for entry in root.iter("item"):
            desc_el = entry.find("description")
            # <description> often wraps raw HTML; itertext() gets the text
            # out of nested elements and entity references alike.
            description = "".join(desc_el.itertext()) if desc_el is not None else ""
            items.append(
                self._item(
                    self.name,
                    entry.findtext("title") or "(untitled)",
                    self._strip_html(description),
                    url=entry.findtext("link") or feed_url,
                    author=entry.findtext("author"),
                    published_at=parse_timestamp(entry.findtext("pubDate")),
                    feed=feed_url,
                )
            )
        return items

class HackerNewsConnector(SourceConnector):
    """Hacker News connector via the official Firebase API (free, no auth).

    ``fetch()`` with no query returns the top stories; with a query it uses
    the Algolia HN Search API. ``fetch_comments()`` retrieves a story's
    comment tree (flattened, depth-capped).
    """

    name = "hackernews"

    def _health_url(self) -> str:
        return "https://hacker-news.firebaseio.com/v0/maxitem.json"

    @staticmethod
    def _strip_html(text: str) -> str:
        return re.sub(r"<[^>]+>", " ", text or "").replace("&amp;", "&").strip()

    async def fetch_top(self, limit: int = 20) -> list[ResearchItem]:
        """Fetch the current top stories."""
        cached = self._cache_get(f"top:{limit}")
        if cached is not None:
            return cached
        story_ids = await self._get_json(
            "https://hacker-news.firebaseio.com/v0/topstories.json"
        )
        items: list[ResearchItem] = []
        for story_id in story_ids[:limit]:
            try:
                story = await self._get_json(
                    f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
                )
            except httpx.HTTPError as exc:
                logger.warning("hn story %s failed: %s", story_id, exc)
                continue
            if not story:
                continue
            items.append(self._story_to_item(story))
        self._cache_put(f"top:{limit}", items)
        return items

    async def fetch_comments(self, story_id: int, limit: int = 20) -> list[ResearchItem]:
        """Fetch (flattened) comments for a story."""
        story = await self._get_json(
            f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
        )
        comments: list[ResearchItem] = []

        async def walk(kids: list[int], depth: int) -> None:
            if depth > 3 or len(comments) >= limit:
                return
            for kid in kids[:limit]:
                try:
                    comment = await self._get_json(
                        f"https://hacker-news.firebaseio.com/v0/item/{kid}.json"
                    )
                except httpx.HTTPError:
                    continue
                if not comment:
                    continue
                comments.append(
                    self._item(
                        self.name,
                        f"Comment on: {story.get('title', story_id)}",
                        self._strip_html(comment.get("text") or ""),
                        url=f"https://news.ycombinator.com/item?id={kid}",
                        author=comment.get("by"),
                        published_at=parse_timestamp(str(comment.get("time")))
                        if comment.get("time")
                        else None,
                        kind="comment",
                        depth=depth,
                    )
                )
                await walk(comment.get("kids") or [], depth + 1)

        await walk(story.get("kids") or [], 0)
        return comments

    async def _fetch(self, query: str | None) -> list[ResearchItem]:
        if not query:
            return await self.fetch_top()
        data = await self._get_json(
            "https://hn.algolia.com/api/v1/search",
            params={"query": query, "hitsPerPage": 20},
        )
        return [
            self._item(
                self.name,
                hit.get("title") or hit.get("story_title") or "(untitled)",
                self._strip_html(hit.get("story_text") or hit.get("comment_text") or ""),
                url=hit.get("url")
                or f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                author=hit.get("author"),
                published_at=parse_timestamp(hit.get("created_at")),
                points=hit.get("points") or 0,
                num_comments=hit.get("num_comments") or 0,
            )
            for hit in data.get("hits", [])
        ]

    def _story_to_item(self, story: dict) -> ResearchItem:
        return self._item(
            self.name,
            story.get("title") or "(untitled)",
            self._strip_html(story.get("text") or ""),
            url=story.get("url")
            or f"https://news.ycombinator.com/item?id={story.get('id')}",
            author=story.get("by"),
            published_at=parse_timestamp(str(story.get("time")))
            if story.get("time")
            else None,
            points=story.get("score", 0),
            num_comments=story.get("descendants", 0),
            kind="story",
        )
class HuggingFaceConnector(SourceConnector):
    """Model registry connector: trending/notable models from the HF Hub.

    Uses the public models API (``sort=trendingScore``) — no authentication
    required. Each model becomes a ResearchItem whose content lists its tags,
    downloads and pipeline so the relevance engine can judge it.
    """

    name = "huggingface"

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        *,
        max_models: int = 5,
        **kwargs,
    ) -> None:
        super().__init__(client, **kwargs)
        self._max_models = max(1, min(max_models, 50))

    def _health_url(self) -> str:
        return "https://huggingface.co/api/models?limit=1"

    async def _fetch(self, query: str | None) -> list[ResearchItem]:
        params: dict[str, Any] = {
            "sort": "trendingScore",
            "direction": "-1",
            "limit": self._max_models,
        }
        if query:
            params["search"] = query
        data = await self._get_json("https://huggingface.co/api/models", params=params)
        items: list[ResearchItem] = []
        for model in data:
            model_id = model.get("id") or model.get("modelId")
            if not model_id:
                continue
            tags = model.get("tags") or []
            content = " ".join(
                part
                for part in (
                    model.get("description") or "",
                    "tags: " + ", ".join(tags),
                    f"downloads: {model.get('downloads', 0)}, likes: {model.get('likes', 0)}",
                )
                if part
            )
            items.append(
                self._item(
                    self.name,
                    model_id,
                    content,
                    url=f"https://huggingface.co/{model_id}",
                    author=model_id.split("/")[0] if "/" in model_id else None,
                    published_at=parse_timestamp(model.get("lastModified")),
                    downloads=model.get("downloads", 0),
                    likes=model.get("likes", 0),
                    tags=tags,
                    kind="model",
                )
            )
        return items


def build_connectors(source_config: dict | None = None) -> list[SourceConnector]:
    """Instantiate the enabled connector set from a source configuration.

    ``source_config`` follows the shape of
    :data:`mysti.research.sources.DEFAULT_SOURCE_CONFIG`. RSS feeds fall back
    to ``~/.config/mysti/feeds.txt`` when the config lists none, preserving
    the Phase 0 behaviour.
    """
    config = source_config or {}
    connectors: list[SourceConnector] = []

    github_cfg = config.get("github") or {}
    if github_cfg.get("enabled", True):
        connectors.append(GitHubConnector())

    arxiv_cfg = config.get("arxiv") or {}
    if arxiv_cfg.get("enabled", True):
        connectors.append(ArxivConnector(categories=list(arxiv_cfg.get("categories") or [])))

    rss_cfg = config.get("rss") or {}
    if rss_cfg.get("enabled", True):
        feeds = list(rss_cfg.get("feeds") or [])
        if not feeds:
            feeds = load_feeds()
        if feeds:
            connectors.append(RSSConnector(feeds=feeds))

    hn_cfg = config.get("hackernews") or {}
    if hn_cfg.get("enabled", True):
        connectors.append(HackerNewsConnector())

    hf_cfg = config.get("huggingface") or {}
    if hf_cfg.get("enabled", True):
        connectors.append(HuggingFaceConnector(max_models=int(hf_cfg.get("max_models", 5))))

    return connectors
