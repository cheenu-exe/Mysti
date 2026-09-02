"""Tests for research source connectors (all HTTP mocked)."""

import asyncio

import httpx

from mysti.research.connectors import (
    ArxivConnector,
    GitHubConnector,
    HackerNewsConnector,
    RSSConnector,
    load_feeds,
    parse_timestamp,
)

# ----------------------------------------------------------------- fixtures

GITHUB_SEARCH = {
    "items": [
        {
            "full_name": "acme/cool-repo",
            "description": "A cool security tool",
            "html_url": "https://github.com/acme/cool-repo",
            "stargazers_count": 1234,
            "language": "Python",
            "created_at": "2026-08-30T10:00:00Z",
            "owner": {"login": "acme"},
        }
    ]
}

GITHUB_EVENTS = [
    {
        "type": "PushEvent",
        "repo": {"name": "acme/cool-repo"},
        "payload": {"description": "pushed commits"},
        "created_at": "2026-08-31T12:00:00Z",
    }
]

ARXIV_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2608.12345v1</id>
    <title>A Study of Adversarial Machine Learning</title>
    <summary>We study adversarial robustness of neural networks.</summary>
    <published>2026-08-29T00:00:00Z</published>
    <author><name>Ada Lovelace</name></author>
    <author><name>Alan Turing</name></author>
    <category term="cs.CR"/>
    <category term="cs.LG"/>
    <arxiv:primary_category term="cs.CR"/>
  </entry>
</feed>
"""

ATOM_FEED = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>DevSecOps Weekly Digest</title>
    <summary>News about &amp; security</summary>
    <link href="https://example.com/post/1"/>
    <updated>2026-08-31T09:00:00Z</updated>
    <author><name>Feed Author</name></author>
  </entry>
</feed>
"""

RSS_FEED = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item>
    <title>Old-school RSS Post</title>
    <description><p>Hello &amp; welcome</p></description>
    <link>https://example.org/rss-post</link>
    <pubDate>Mon, 31 Aug 2026 08:00:00 GMT</pubDate>
  </item>
</channel></rss>
"""

HN_TOP = [101, 102]
HN_ITEM_101 = {"id": 101, "title": "Show HN: encrypted memory", "url": "https://ex.co/a",
               "by": "alice", "time": 1796000000, "score": 42, "descendants": 7,
               "kids": [201]}
HN_ITEM_201 = {"id": 201, "text": "Great <b>project</b> &amp; useful", "by": "bob",
               "time": 1796000100}
HN_ALGOLIA = {"hits": [{"title": "CTF writeup", "comment_text": "nice",
                        "objectID": "303", "author": "carol",
                        "created_at": "2026-08-30T00:00:00Z", "points": 10,
                        "num_comments": 2}]}


def make_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# ------------------------------------------------------------------- GitHub


async def test_github_trending():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "api.github.com" in str(request.url)
        return httpx.Response(200, json=GITHUB_SEARCH)

    connector = GitHubConnector(make_client(handler), min_interval=0)
    items = await connector.fetch_trending()
    assert len(items) == 1
    item = items[0]
    assert item.source == "github"
    assert item.title == "acme/cool-repo"
    assert item.metadata["stars"] == 1234
    assert item.published_at is not None
    await connector.aclose()


async def test_github_user_activity():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=GITHUB_EVENTS)

    connector = GitHubConnector(make_client(handler), min_interval=0)
    items = await connector.fetch_user_activity("acme")
    assert items[0].title.startswith("PushEvent")
    assert items[0].author == "acme"
    await connector.aclose()


async def test_github_fetch_with_query():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=GITHUB_SEARCH)

    connector = GitHubConnector(make_client(handler), min_interval=0)
    items = await connector.fetch("security")
    assert items and items[0].source == "github"
    await connector.aclose()


# -------------------------------------------------------------------- arXiv


async def test_arxiv_parse():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=ARXIV_ATOM)

    connector = ArxivConnector(make_client(handler), min_interval=0)
    items = await connector.fetch("adversarial")
    assert len(items) == 1
    item = items[0]
    assert item.source == "arxiv"
    assert "Adversarial" in item.title
    assert item.author == "Ada Lovelace"
    assert item.metadata["authors"] == ["Ada Lovelace", "Alan Turing"]
    assert item.metadata["primary_category"] == "cs.CR"
    assert "cs.LG" in item.metadata["categories"]


async def test_arxiv_search_with_categories():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "cat:cs.CR" in request.url.params["search_query"]
        return httpx.Response(200, text=ARXIV_ATOM)

    connector = ArxivConnector(make_client(handler), min_interval=0)
    items = await connector.search("adversarial", categories=["cs.CR"])
    assert len(items) == 1


# ---------------------------------------------------------------------- RSS


async def test_rss_atom_and_rss20():
    def handler(request: httpx.Request) -> httpx.Response:
        text = ATOM_FEED if "atom" in str(request.url) else RSS_FEED
        return httpx.Response(200, text=text)

    connector = RSSConnector(
        make_client(handler),
        feeds=["https://f.example/atom", "https://f.example/rss"],
        min_interval=0,
    )
    items = await connector.fetch()
    titles = {item.title for item in items}
    assert "DevSecOps Weekly Digest" in titles
    assert "Old-school RSS Post" in titles
    # HTML is stripped and entities decoded in RSS description
    rss_item = next(i for i in items if i.title == "Old-school RSS Post")
    assert "Hello & welcome" in rss_item.content
    assert rss_item.published_at is not None


async def test_rss_query_filtering():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=ATOM_FEED)

    connector = RSSConnector(
        make_client(handler), feeds=["https://f.example/atom"], min_interval=0
    )
    matching = await connector.fetch("devsecops")
    assert len(matching) == 1
    none = await connector.fetch("quantum")
    assert none == []


async def test_rss_broken_feed_is_skipped():
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if "bad" in str(request.url):
            return httpx.Response(500)
        return httpx.Response(200, text=RSS_FEED)

    connector = RSSConnector(
        make_client(handler),
        feeds=["https://f.example/bad", "https://f.example/good"],
        min_interval=0,
    )
    items = await connector.fetch()
    assert len(items) == 1  # good feed still parsed despite 500 on the bad one
    assert len(calls) == 2


def test_load_feeds_from_file(tmp_path):
    feeds_file = tmp_path / "feeds.txt"
    feeds_file.write_text(
        "# comment\nhttps://a.example/rss\n\nhttps://b.example/atom\n", encoding="utf-8"
    )
    assert load_feeds(feeds_file) == ["https://a.example/rss", "https://b.example/atom"]
    assert load_feeds(tmp_path / "missing.txt") == []


# ------------------------------------------------------------- Hacker News


async def test_hackernews_top_and_comments():
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("topstories.json"):
            return httpx.Response(200, json=HN_TOP)
        if "item/101.json" in url:
            return httpx.Response(200, json=HN_ITEM_101)
        if "item/201.json" in url:
            return httpx.Response(200, json=HN_ITEM_201)
        return httpx.Response(404)

    connector = HackerNewsConnector(make_client(handler), min_interval=0)
    stories = await connector.fetch()
    assert len(stories) == 1
    story = stories[0]
    assert story.source == "hackernews"
    assert story.metadata["points"] == 42
    assert story.url == "https://ex.co/a"
    comments = await connector.fetch_comments(101)
    assert len(comments) == 1
    assert comments[0].author == "bob"
    assert "project" in comments[0].content and "<b>" not in comments[0].content
    await connector.aclose()


async def test_hackernews_search():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "hn.algolia.com" in str(request.url)
        return httpx.Response(200, json=HN_ALGOLIA)

    connector = HackerNewsConnector(make_client(handler), min_interval=0)
    items = await connector.fetch("CTF")
    assert len(items) == 1
    assert items[0].title == "CTF writeup"
    await connector.aclose()


# ------------------------------------------------------- caching & resilience


async def test_fetch_caches_for_an_hour():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json=GITHUB_SEARCH)

    connector = GitHubConnector(make_client(handler), min_interval=0, cache_ttl=3600)
    first = await connector.fetch("security")
    second = await connector.fetch("security")
    assert calls["n"] == 1  # second call served from cache
    assert first == second
    await connector.aclose()


async def test_cache_expires_after_ttl():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json=GITHUB_SEARCH)

    connector = GitHubConnector(make_client(handler), min_interval=0, cache_ttl=0.01)
    await connector.fetch("security")
    await asyncio.sleep(0.05)
    await connector.fetch("security")
    assert calls["n"] == 2  # TTL elapsed -> refetched
    await connector.aclose()


async def test_network_error_returns_empty_not_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    connector = GitHubConnector(make_client(handler), min_interval=0)
    assert await connector.fetch("anything") == []
    await connector.aclose()


async def test_health_check():
    def ok(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("nope")

    healthy = GitHubConnector(make_client(ok), min_interval=0)
    assert await healthy.health_check() is True
    await healthy.aclose()
    unhealthy = GitHubConnector(make_client(down), min_interval=0)
    assert await unhealthy.health_check() is False
    await unhealthy.aclose()


async def test_rate_limiter_enforces_interval():
    import time

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=GITHUB_SEARCH)

    connector = GitHubConnector(make_client(handler), min_interval=0.05)
    started = time.monotonic()
    await connector.fetch("a")
    await connector.fetch("b")
    elapsed = time.monotonic() - started
    assert elapsed >= 0.05  # second request waited for the interval
    await connector.aclose()


def test_parse_timestamp_variants():
    assert parse_timestamp("2026-08-31T12:00:00Z").startswith("2026-08-31T12:00:00+00:00")
    assert parse_timestamp("2026-08-31T12:00:00+00:00").startswith("2026-08-31")
    assert parse_timestamp("garbage") is None
    assert parse_timestamp(None) is None
    assert parse_timestamp("") is None
