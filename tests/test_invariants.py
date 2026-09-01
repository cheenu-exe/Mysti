"""Security invariant tests: the properties that must never regress.

1. Remote storage only ever receives ciphertext (no plaintext content).
2. The master key is never uploaded anywhere.
3. The cache holds ciphertext only.
4. Deleted records are excluded from search results.
"""

import pytest

from mysti.memory import envelope
from mysti.memory.service import INDEX_KEY, record_path

SECRET = "Mysti-9:the-private-plaintext-payload-42"


async def _populate(memory):
    return [
        await memory.store("personal", SECRET, {"tags": ["test"]}),
        await memory.store("technical", "note about rust build tooling"),
    ]


async def test_no_plaintext_anywhere_in_remote_storage(ctx):
    records = await _populate(ctx.memory)
    session_id = await ctx.conversations.start_session()
    await ctx.conversations.add_message(session_id, "user", SECRET)

    for key in await ctx.storage.list(""):
        blob = await ctx.storage.get(key)
        assert SECRET.encode() not in blob, f"plaintext leaked into remote object {key}"
    assert records  # sanity


async def test_master_key_never_uploaded(ctx):
    master = await ctx.keys.get_master_key()
    for key in await ctx.storage.list(""):
        blob = await ctx.storage.get(key)
        assert master not in blob, f"master key leaked into remote object {key}"


async def test_cache_holds_ciphertext_only(ctx):
    records = await _populate(ctx.memory)
    await ctx.memory.retrieve(records[0].id)
    path = record_path(records[0].id, "personal")
    cached = ctx.cache.get(path)
    assert cached is not None
    assert cached.startswith(envelope.MAGIC)
    assert SECRET.encode() not in cached


async def test_deleted_records_excluded_from_search_and_retrieval(ctx):
    record = (await _populate(ctx.memory))[0]
    await ctx.memory.delete(record.id)
    assert await ctx.memory.search("private-plaintext") == []
    from mysti.exceptions import RecordNotFoundError

    with pytest.raises(RecordNotFoundError):
        await ctx.memory.retrieve(record.id)


async def test_index_is_encrypted_and_content_free(ctx):
    await _populate(ctx.memory)
    blob = await ctx.storage.get(INDEX_KEY)
    assert b"rust build tooling" not in blob
    assert SECRET.encode() not in blob


async def test_audit_log_contains_no_content(ctx):
    records = await _populate(ctx.memory)
    await ctx.memory.retrieve(records[0].id)
    log_text = (ctx.settings.data_dir / "audit.jsonl").read_text(encoding="utf-8")
    assert SECRET not in log_text
    assert ctx.audit.verify() is True
