"""Memory service tests: store, retrieve, search, delete, categories, audit."""

import hashlib

import pytest

from mysti.exceptions import EncryptionError, RecordNotFoundError, ValidationError
from mysti.memory import envelope
from mysti.memory.service import INDEX_KEY, record_path


async def test_store_and_retrieve_roundtrip(memory):
    record = await memory.store(
        "personal", "my favorite coffee is flat white", {"tags": ["coffee"]}
    )
    fetched = await memory.retrieve(record.id)
    assert fetched.content == "my favorite coffee is flat white"
    assert fetched.category == "personal"
    assert fetched.metadata == {"tags": ["coffee"]}


async def test_retrieve_missing_raises(memory):
    with pytest.raises(RecordNotFoundError):
        await memory.retrieve("00000000-0000-0000-0000-000000000000")


async def test_unknown_category_rejected(memory):
    with pytest.raises(ValidationError):
        await memory.store("not-a-category", "x")
    with pytest.raises(ValidationError):
        await memory.store("meta", "reserved categories are not user-facing")


async def test_record_size_limit(memory):
    with pytest.raises(ValidationError):
        await memory.store("personal", "x" * (memory._max_record_bytes + 1))


async def test_remote_sees_only_ciphertext(memory, storage):
    secret = "the launch codes are 12345"
    record = await memory.store("personal", secret)
    blob = await storage.get(record_path(record.id, "personal"))
    assert secret.encode() not in blob
    assert blob.startswith(envelope.MAGIC)
    index_blob = await storage.get(INDEX_KEY)
    assert secret.encode() not in index_blob
    assert b"launch" not in index_blob


async def test_search_finds_content(memory):
    await memory.store("technical", "postgresql tuning guide")
    await memory.store("personal", "dentist appointment tuesday")
    hits = await memory.search("postgres")
    assert len(hits) == 1
    assert "postgresql" in hits[0].preview


async def test_search_category_filter_and_limit(memory):
    for i in range(5):
        await memory.store("technical", f"rust note {i}")
        await memory.store("personal", f"rust memory {i}")
    hits = await memory.search("rust", category="personal", limit=2)
    assert len(hits) == 2
    assert all(hit.category == "personal" for hit in hits)


async def test_search_excludes_deleted(memory):
    record = await memory.store("ideas", "quantum journaling app")
    await memory.delete(record.id)
    assert await memory.search("quantum") == []


async def test_delete_is_soft(memory):
    record = await memory.store("projects", "garden sensor firmware")
    await memory.delete(record.id)
    with pytest.raises(RecordNotFoundError):
        await memory.retrieve(record.id)
    counts = await memory.list_categories()
    assert counts.get("projects", 0) == 0


async def test_list_categories_counts(memory):
    await memory.store("personal", "a")
    await memory.store("personal", "b")
    await memory.store("ideas", "c")
    counts = await memory.list_categories()
    assert counts == {"personal": 2, "ideas": 1}


async def test_integrity_hash_detects_tampering(memory, storage, cache):
    record = await memory.store("personal", "integrity matters")
    path = record_path(record.id, "personal")
    blob = bytearray(await storage.get(path))
    blob[-2] ^= 0x55
    await storage.put(path, bytes(blob))
    cache.clear()  # otherwise the pristine cached blob would mask the tampering
    with pytest.raises(EncryptionError):
        await memory.retrieve(record.id)


async def test_content_hash_matches_plaintext(memory):
    record = await memory.store("personal", "hash me")
    fetched = await memory.retrieve(record.id)
    assert hashlib.sha256(fetched.content.encode()).hexdigest()


async def test_audit_trail_written(memory, audit):
    record = await memory.store("personal", "audited")
    await memory.retrieve(record.id)
    await memory.search("audited")
    await memory.delete(record.id)
    actions = [entry["action"] for entry in audit.tail(50)]
    assert "memory.store" in actions
    assert "memory.retrieve" in actions
    assert "memory.search" in actions
    assert "memory.delete" in actions
    assert audit.verify() is True
