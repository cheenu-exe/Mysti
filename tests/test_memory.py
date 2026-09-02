"""Phase 1 integration tests: end-to-end memory workflows.

Covers structured storage, semantic search, conversation memory extraction,
consolidation and category stats — exercised through the public services the
same way the CLI/API layer uses them.
"""

import pytest

from mysti.memory.categories import CategoryManager
from mysti.memory.consolidation import MemoryConsolidator
from mysti.memory.embeddings import EmbeddingService, HashingEmbeddingBackend
from mysti.memory.service import MemoryService


@pytest.fixture
async def embedded_memory(keys, storage, cache, audit) -> MemoryService:
    """Memory service wired with the deterministic offline embedder."""
    return MemoryService(
        storage, keys, cache, audit, embeddings=EmbeddingService([HashingEmbeddingBackend()])
    )


# --- structured storage -------------------------------------------------------


async def test_structured_storage_roundtrip(embedded_memory: MemoryService):
    record = await embedded_memory.store(
        "projects",
        "MYSTI phase 1: memory intelligence",
        metadata={"phase": 1},
        tags=["mysti", "roadmap"],
        source="observation",
        importance=8,
    )
    loaded = await embedded_memory.retrieve(record.id)
    assert loaded.id == record.id
    assert loaded.category == "projects"
    assert loaded.content == "MYSTI phase 1: memory intelligence"
    assert loaded.tags == ["mysti", "roadmap"]
    assert loaded.source == "observation"
    assert loaded.importance == 8
    assert loaded.metadata == {"phase": 1}
    assert loaded.content_hash == record.content_hash
    assert loaded.created_at == record.created_at
    assert loaded.embedding is not None
    assert loaded.access_count == 1  # retrieve bumps the access counter
    again = await embedded_memory.retrieve(record.id)
    assert again.access_count == 2
    assert again.last_accessed >= loaded.last_accessed


# --- semantic search ---------------------------------------------------------


async def test_semantic_search_ranks_relevant_first(embedded_memory: MemoryService):
    topics = {
        "personal": "I prefer tea over coffee in the morning",
        "technical": "Docker layer caching speeds up image builds",
        "research": "transformer attention mechanisms explained",
        "ideas": "a smart plant watering system with sensors",
    }
    for category, content in topics.items():
        await embedded_memory.store(category, content)
    hits = await embedded_memory.search("container image build caching", limit=4)
    assert hits, "search should return results"
    assert hits[0].category == "technical"
    assert hits[0].score >= hits[-1].score
    keyword_hits = await embedded_memory.search("transformer", category="research")
    assert keyword_hits and keyword_hits[0].category == "research"


# --- conversation memory -----------------------------------------------------


async def test_conversation_memory_extraction(conversations):
    messages = [
        ("user", "Remember that my deployment target is AWS eu-central-1."),
        ("assistant", "Noted: deployments go to AWS eu-central-1."),
    ]
    session_id = await conversations.start_session()
    for role, content in messages:
        await conversations.add_message(session_id, role, content)
    history = await conversations.get_messages(session_id)
    assert len(history) == 2
    assert history[0].role == "user"
    assert "eu-central-1" in history[0].content
    # conversations live in their own encrypted store with session listing
    sessions = await conversations.list_sessions()
    assert any(s.session_id == session_id for s in sessions)
    assert await conversations.session_exists(session_id)


# --- consolidation -----------------------------------------------------------


async def test_consolidation_removes_duplicates(embedded_memory: MemoryService):
    consolidator = MemoryConsolidator(embedded_memory, embedded_memory._audit)
    await embedded_memory.store("technical", "identical note about redis persistence")
    await embedded_memory.store("technical", "identical note about redis persistence")
    stats = await consolidator.consolidate("technical")
    assert stats["removed"] == 1
    remaining = await embedded_memory.entries("technical")
    assert len(remaining) == 1


# --- categories --------------------------------------------------------------


async def test_category_stats_are_correct(embedded_memory: MemoryService, keys, storage, audit):
    manager = CategoryManager(embedded_memory, keys, storage, audit)
    await embedded_memory.store("ideas", "invention: self-filling water bottle")
    await embedded_memory.store("ideas", "plan: weekend hiking trip")
    listed = {item["name"]: item for item in await manager.list_categories()}
    assert listed["ideas"]["count"] == 2
    assert listed["personal"]["is_default"]
    stats = await manager.get_stats()
    assert stats["total_records"] == 2
    assert stats["categories"]["ideas"]["count"] == 2
    assert stats["categories"]["ideas"]["bytes"] > 0
