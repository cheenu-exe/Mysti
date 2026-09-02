"""Phase 2 integration tests: relevance engine, daily briefing, deep research."""

import json
from datetime import UTC, datetime, timedelta

import pytest

from mysti.exceptions import RecordNotFoundError
from mysti.research.briefing import DailyBriefing
from mysti.research.connectors import SourceConnector
from mysti.research.deep import DeepResearch
from mysti.research.models import ResearchItem
from mysti.research.relevance import RelevanceEngine, load_profile

# ----------------------------------------------------------------- helpers


def make_item(
    title: str,
    source: str = "arxiv",
    content: str = "",
    url: str | None = None,
    author: str | None = None,
    published_at: str | None = None,
    **metadata,
) -> ResearchItem:
    now = datetime.now(UTC).isoformat()
    return ResearchItem(
        id="x", source=source, title=title, content=content, url=url, author=author,
        published_at=published_at or now, fetched_at=now, metadata=metadata,
    )


class FakeConnector(SourceConnector):
    """Deterministic connector returning canned items (no HTTP)."""

    name = "fake"

    def __init__(self, items_by_query: dict[str | None, list[ResearchItem]]) -> None:
        super().__init__(min_interval=0)
        self._items = items_by_query
        self.queries: list[str | None] = []

    async def _fetch(self, query: str | None) -> list[ResearchItem]:
        self.queries.append(query)
        return list(self._items.get(query, []))

    def _health_url(self) -> str:
        return "https://fake.example/health"


PROFILE = {
    "keywords": ["cybersecurity", "CTF", "machine learning", "DevSecOps"],
    "categories": ["cs.CR", "cs.AI", "cs.SE"],
    "importance_threshold": 5,
    "trusted_authors": ["ada"],
}


# --------------------------------------------------------- relevance engine


async def test_score_keyword_title_beats_body():
    engine = RelevanceEngine(profile=PROFILE)
    in_title = make_item("New cybersecurity framework released", source="arxiv")
    in_body = make_item("Weekly digest", content="lots about cybersecurity here",
                        source="arxiv")
    assert await engine.score(in_title) > await engine.score(in_body)


async def test_score_component_ranges():
    engine = RelevanceEngine(profile=PROFILE)
    item = make_item(
        "CTF writeup: machine learning attacks",
        source="arxiv",
        content="cybersecurity DevSecOps",
        author="ada",
        published_at=datetime.now(UTC).isoformat(),
    )
    # keyword 3 (title hits on CTF + machine learning, body hits on the rest)
    # + source 2 + recency 2 + author 2 = 9
    assert await engine.score(item) == pytest.approx(9.0)
    unrelated = make_item("Gardening tips", source="rss",
                          published_at=(datetime.now(UTC) - timedelta(days=365)).isoformat())
    score = await engine.score(unrelated)
    assert 0.0 <= score <= 10.0
    assert score < 2.0  # no keywords, low-quality source, old


async def test_score_recency_decays():
    engine = RelevanceEngine(profile=PROFILE)
    fresh = make_item("CTF", source="hackernews",
                      published_at=datetime.now(UTC).isoformat())
    old = make_item("CTF", source="hackernews",
                    published_at=(datetime.now(UTC) - timedelta(days=90)).isoformat())
    assert await engine.score(fresh) > await engine.score(old)


async def test_score_source_quality_ordering():
    engine = RelevanceEngine(profile=PROFILE)
    scores = []
    for source in ("arxiv", "github", "hackernews", "rss"):
        scores.append(await engine.score(make_item("nothing relevant", source=source)))
    assert scores == sorted(scores, reverse=True)


async def test_score_category_match():
    engine = RelevanceEngine(profile=PROFILE)
    with_cat = make_item("Robustness study", source="arxiv", categories=["cs.CR"])
    without = make_item("Robustness study", source="arxiv", categories=["math.AC"])
    assert await engine.score(with_cat) > await engine.score(without)


async def test_filter_threshold():
    engine = RelevanceEngine(profile=PROFILE)
    items = [
        make_item("cybersecurity CTF machine learning DevSecOps"),
        make_item("Totally unrelated gardening", source="rss"),
        make_item("(untitled)"),
    ]
    kept = await engine.filter(items, min_score=5.0)
    assert len(kept) == 1
    assert "cybersecurity" in kept[0].title


async def test_deduplicate_across_sources():
    engine = RelevanceEngine(profile=PROFILE)
    items = [
        make_item("Same story", source="github", url="https://ex.co/1"),
        make_item("Same story", source="hackernews", url="https://ex.co/1"),
        make_item("Same story", source="rss"),  # no URL -> title fingerprint
        make_item("Different story", source="arxiv", url="https://ex.co/2"),
    ]
    unique = await engine.deduplicate(items)
    assert len(unique) == 3  # URL dupes collapse; no-URL title-only kept
    assert unique[0].source == "github"  # first occurrence kept


async def test_rank_orders_by_score():
    engine = RelevanceEngine(profile=PROFILE)
    low = make_item("Gardening", source="rss")
    high = make_item("CTF cybersecurity", source="arxiv")
    ranked = await engine.rank([low, high])
    assert ranked[0].title.startswith("CTF")


def test_load_profile_defaults_and_file(tmp_path):
    defaults = load_profile(tmp_path / "missing.json")
    assert defaults["keywords"] == ["cybersecurity", "CTF", "machine learning", "DevSecOps"]
    path = tmp_path / "interests.json"
    path.write_text(json.dumps({"keywords": ["rust"], "importance_threshold": 7}),
                    encoding="utf-8")
    profile = load_profile(path)
    assert profile["keywords"] == ["rust"]
    assert profile["importance_threshold"] == 7
    assert profile["categories"]  # defaults preserved for unspecified keys


# ----------------------------------------------------------- daily briefing


@pytest.fixture
async def briefing_service(keys, storage, audit):
    connector = FakeConnector(
        {
            None: [
                make_item("cybersecurity CTF championship results", source="hackernews",
                          url="https://ex.co/ctf"),
                make_item("machine learning for vulnerability detection", source="arxiv",
                          url="https://arxiv.org/abs/1", categories=["cs.CR"]),
                make_item("New DevSecOps pipeline tool", source="github",
                          url="https://github.com/x/y", author="ada"),
                make_item("Gardening weekly", source="rss", url="https://rss.ex/1"),
            ]
        }
    )
    engine = RelevanceEngine(profile=PROFILE)
    return DailyBriefing([connector], engine, keys, storage, audit, min_score=5.0)


async def test_briefing_generation_format(briefing_service):
    data = await briefing_service.generate_briefing()
    assert data["date"] == datetime.now(UTC).strftime("%Y-%m-%d")
    assert set(data) >= {"date", "summary", "highlights", "categories", "stats"}
    stats = data["stats"]
    assert stats["items_scanned"] == 4
    assert stats["sources_checked"] == 1
    # Low-relevance item filtered out
    titles = [h["title"] for h in data["highlights"]]
    assert "Gardening weekly" not in titles
    assert any("CTF" in t for t in titles)
    # Each highlight has the documented shape
    for highlight in data["highlights"]:
        assert {"title", "source", "relevance", "url", "bucket"} <= set(highlight)
        assert 0.0 <= highlight["relevance"] <= 10.0


async def test_briefing_categorized_buckets(briefing_service):
    data = await briefing_service.generate_briefing()
    all_titles = {h["title"] for bucket in data["categories"].values() for h in bucket}
    assert all_titles == {h["title"] for h in data["highlights"]}
    buckets = {h["bucket"] for h in data["highlights"]}
    assert buckets <= {"cybersecurity", "ai/ml", "development", "general"}


async def test_briefing_persisted_encrypted_and_retrievable(briefing_service, storage):
    data = await briefing_service.generate_briefing()
    date = data["date"]
    # Stored as ciphertext at mysti/briefings/{date}.enc
    blob = await storage.get(f"mysti/briefings/{date}.enc")
    assert b"highlights" not in blob  # never plaintext on the storage backend
    # Round-trips through get_briefing
    loaded = await briefing_service.get_briefing(date)
    assert loaded["summary"] == data["summary"]
    assert loaded["stats"] == data["stats"]


async def test_briefing_get_past_missing_raises(briefing_service):
    with pytest.raises(RecordNotFoundError):
        await briefing_service.get_briefing("1999-01-01")


async def test_briefing_list_recent(briefing_service):
    await briefing_service.generate_briefing()
    recent = await briefing_service.list_briefings(days=7)
    assert len(recent) == 1
    assert recent[0]["date"] == datetime.now(UTC).strftime("%Y-%m-%d")
    assert "items_selected" in recent[0]


async def test_briefing_empty_sources_yields_empty_summary(keys, storage, audit):
    connector = FakeConnector({None: []})
    engine = RelevanceEngine(profile=PROFILE)
    service = DailyBriefing([connector], engine, keys, storage, audit)
    data = await service.generate_briefing()
    assert data["stats"]["items_scanned"] == 0
    assert data["highlights"] == []
    assert "nothing met the relevance threshold" in data["summary"]


# ------------------------------------------------------------ deep research


@pytest.fixture
def deep_connector():
    return FakeConnector(
        {
            "adversarial machine learning": [
                make_item("Adversarial machine learning survey", source="arxiv",
                          url="https://arxiv.org/abs/100", categories=["cs.LG"],
                          content="A survey of adversarial robustness."),
                make_item("Adversarial machine learning survey", source="github",
                          url="https://arxiv.org/abs/100"),  # corroboration
            ],
        }
    )


@pytest.fixture
async def deep_service(deep_connector, keys, storage, audit):
    engine = RelevanceEngine(profile=PROFILE)
    return DeepResearch([deep_connector], engine, keys, storage, audit)


async def test_deep_research_report_structure(deep_service):
    session = await deep_service.research("adversarial machine learning", depth=1)
    assert session.topic == "adversarial machine learning"
    assert session.completed_at is not None
    assert session.sources_consulted == 1
    assert session.findings, "expected findings from mocked source"
    for section in (
        "# Research Report",
        "## Executive Summary",
        "## Key Findings",
        "## Detailed Analysis",
        "## Sources",
        "## Confidence Assessment",
    ):
        assert section in session.report


async def test_deep_research_corroboration(deep_service):
    session = await deep_service.research("adversarial machine learning", depth=1)
    top = session.findings[0]
    # Same URL reported by two distinct sources -> citation list has both
    assert len(top.citations) == 2
    assert top.confidence > 0.5


async def test_deep_research_depth_expands_queries(deep_connector, keys, storage, audit):
    deep_connector._items["survey"] = [
        make_item("Second wave: survey follow-up", source="arxiv",
                  url="https://arxiv.org/abs/200")
    ]
    engine = RelevanceEngine(profile=PROFILE)
    service = DeepResearch([deep_connector], engine, keys, storage, audit)
    session = await service.research("adversarial machine learning", depth=2)
    queried = [q for q in deep_connector.queries if q is not None]
    assert "adversarial machine learning" in queried
    assert any("survey" in q for q in queried[1:])  # expansion happened
    assert len(session.findings) >= 2


async def test_deep_research_depth_clamped(deep_connector, keys, storage, audit):
    engine = RelevanceEngine(profile=PROFILE)
    service = DeepResearch([deep_connector], engine, keys, storage, audit)
    session = await service.research("adversarial machine learning", depth=99)
    assert session.depth == 5


async def test_deep_research_session_persisted_encrypted(deep_service, storage):
    session = await deep_service.research("adversarial machine learning", depth=1)
    blob = await storage.get(f"mysti/research/{session.id}.enc")
    assert b"Executive Summary" not in blob  # encrypted at rest


async def test_deep_research_get_report_roundtrip(deep_service):
    session = await deep_service.research("adversarial machine learning", depth=1)
    data = await deep_service.get_report(session.id)
    assert data["id"] == session.id
    assert data["report"] == session.report
    assert data["confidence"] == session.confidence
    assert data["findings"][0]["item"]["title"]


async def test_deep_research_get_report_missing(deep_service):
    with pytest.raises(RecordNotFoundError):
        await deep_service.get_report("no-such-session")


async def test_deep_research_list_sessions(deep_service):
    first = await deep_service.research("adversarial machine learning", depth=1)
    second = await deep_service.research("quantum gardening", depth=1)
    all_sessions = await deep_service.list_sessions()
    assert {s["id"] for s in all_sessions} == {first.id, second.id}
    filtered = await deep_service.list_sessions(topic="adversarial")
    assert [s["id"] for s in filtered] == [first.id]


async def test_deep_research_no_findings(deep_connector, keys, storage, audit):
    deep_connector._items = {}
    engine = RelevanceEngine(profile=PROFILE)
    service = DeepResearch([deep_connector], engine, keys, storage, audit)
    session = await service.research("unknown topic", depth=1)
    assert session.findings == []
    assert session.confidence == 0.0
    assert "No relevant findings" in session.report
