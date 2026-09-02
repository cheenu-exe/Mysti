"""Tests for memory consolidation (dedup, merge, importance re-scoring)."""

import pytest

from mysti.exceptions import RecordNotFoundError
from mysti.memory.consolidation import MemoryConsolidator
from mysti.memory.embeddings import EmbeddingService, HashingEmbeddingBackend
from mysti.memory.service import MemoryService


@pytest.fixture
async def embedded_memory(keys, storage, cache, audit) -> MemoryService:
    """Memory service with the deterministic hashing embedder attached."""
    embeddings = EmbeddingService([HashingEmbeddingBackend()], cache_size=256)
    return MemoryService(storage, keys, cache, audit, embeddings=embeddings)


@pytest.fixture
async def consolidator(embedded_memory: MemoryService, audit) -> MemoryConsolidator:
    return MemoryConsolidator(embedded_memory, audit)


async def test_deduplicate_removes_exact_duplicates(
    embedded_memory: MemoryService, consolidator: MemoryConsolidator
):
    first = await embedded_memory.store("technical", "docker layer caching explained")
    second = await embedded_memory.store("technical", "docker layer caching explained")
    removed = await consolidator.deduplicate("technical")
    assert removed == 1
    ids = {entry.id for entry in await embedded_memory.entries("technical")}
    assert ids == {second.id}  # newest kept, oldest removed
    with pytest.raises(RecordNotFoundError):
        await embedded_memory.retrieve(first.id)


async def test_deduplicate_noop_when_unique(consolidator: MemoryConsolidator, embedded_memory):
    await embedded_memory.store("ideas", "idea one")
    await embedded_memory.store("ideas", "idea two")
    assert await consolidator.deduplicate() == 0


async def test_consolidate_merges_similar_memories(
    embedded_memory: MemoryService, consolidator: MemoryConsolidator
):
    await embedded_memory.store(
        "technical", "docker layer caching speeds up builds", tags=["docker"]
    )
    await embedded_memory.store(
        "technical", "docker layer caching speeds builds", tags=["perf"]
    )
    stats = await consolidator.consolidate("technical")
    assert stats["merged"] == 1
    assert stats["updated"] == 1
    remaining = await embedded_memory.entries("technical")
    assert len(remaining) == 1
    content = await embedded_memory.decrypt_content(remaining[0])
    assert "docker layer caching speeds up builds" in content
    assert "docker layer caching speeds builds" in content
    assert set(remaining[0].tags) == {"docker", "perf"}
    assert remaining[0].metadata.get("merged_from")


async def test_consolidate_keeps_dissimilar_memories(
    embedded_memory: MemoryService, consolidator: MemoryConsolidator
):
    await embedded_memory.store("personal", "birthday is in march")
    await embedded_memory.store("research", "transformer attention paper review")
    stats = await consolidator.consolidate()
    assert stats["merged"] == 0
    assert len(await embedded_memory.entries()) == 2


async def test_update_importance_rewards_access(
    embedded_memory: MemoryService, consolidator: MemoryConsolidator
):
    record = await embedded_memory.store("projects", "mysti roadmap draft")
    for _ in range(5):
        await embedded_memory.retrieve(record.id)
    changed = await consolidator.update_importance("projects")
    entry = await embedded_memory.get_entry(record.id)
    assert changed == 1
    assert entry.importance == 6


async def test_update_importance_clamps_at_maximum(
    embedded_memory: MemoryService, consolidator: MemoryConsolidator
):
    record = await embedded_memory.store("ideas", "venn diagram of ideas", importance=10)
    for _ in range(10):
        await embedded_memory.retrieve(record.id)
    await consolidator.update_importance()
    entry = await embedded_memory.get_entry(record.id)
    assert entry.importance == 10  # never exceeds the maximum
