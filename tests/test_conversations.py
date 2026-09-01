"""Conversation store tests: sessions, messages, context building."""

import pytest

from mysti.exceptions import RecordNotFoundError, ValidationError


async def test_start_session_and_add_messages(conversations):
    session_id = await conversations.start_session()
    first = await conversations.add_message(session_id, "user", "hello mysti")
    await conversations.add_message(session_id, "assistant", "hello!")
    assert first.session_id == session_id
    messages = await conversations.get_messages(session_id)
    assert [m.content for m in messages] == ["hello mysti", "hello!"]
    assert [m.role for m in messages] == ["user", "assistant"]


async def test_messages_encrypted_at_rest(conversations, storage):
    session_id = await conversations.start_session()
    await conversations.add_message(session_id, "user", "top secret plan")
    keys = await storage.list(f"mysti/conversations/{session_id}/")
    raw = b"".join([await storage.get(key) for key in keys])
    assert b"top secret plan" not in raw


async def test_get_messages_pagination(conversations):
    session_id = await conversations.start_session()
    for i in range(5):
        await conversations.add_message(session_id, "user", f"message {i}")
    page = await conversations.get_messages(session_id, limit=2, offset=2)
    assert [m.content for m in page] == ["message 2", "message 3"]


async def test_invalid_role_rejected(conversations):
    session_id = await conversations.start_session()
    with pytest.raises(ValidationError):
        await conversations.add_message(session_id, "tool", "nope")


async def test_unknown_session_rejected(conversations):
    with pytest.raises(RecordNotFoundError):
        await conversations.add_message("no-such-session", "user", "hi")
    with pytest.raises(RecordNotFoundError):
        await conversations.get_messages("no-such-session")


async def test_build_context_respects_budget(conversations):
    session_id = await conversations.start_session()
    for _ in range(10):
        await conversations.add_message(session_id, "user", "x" * 100)
    context = await conversations.build_context(session_id, max_tokens=10)  # ~40 chars
    assert len(context) <= 2
    assert context[-1]["content"] == "x" * 100  # most recent kept


async def test_build_context_preserves_order(conversations):
    session_id = await conversations.start_session()
    await conversations.add_message(session_id, "user", "first")
    await conversations.add_message(session_id, "assistant", "second")
    context = await conversations.build_context(session_id)
    assert [m["content"] for m in context] == ["first", "second"]
    assert [m["role"] for m in context] == ["user", "assistant"]


async def test_list_sessions_and_counts(conversations):
    first = await conversations.start_session()
    await conversations.add_message(first, "user", "hi")
    second = await conversations.start_session()
    assert second != first
    sessions = await conversations.list_sessions()
    assert len(sessions) == 2
    counts = {s.message_count for s in sessions}
    assert counts == {0, 1}


async def test_audit_trail(conversations, audit):
    session_id = await conversations.start_session()
    await conversations.add_message(session_id, "user", "logged")
    actions = [entry["action"] for entry in audit.tail(10)]
    assert "conversation.start" in actions
    assert "conversation.add_message" in actions
    assert audit.verify() is True
