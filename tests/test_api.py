"""API endpoint tests (in-process, no network, no paid services)."""

import pytest
from fastapi.testclient import TestClient

from mysti.api.app import create_app


class FakeLLM:
    """Deterministic LLM stand-in for API tests."""

    async def complete(self, messages, model=None):
        return f"echo: {messages[-1]['content']}"

    async def aclose(self):
        return None


@pytest.fixture
def client(ctx):
    with TestClient(create_app(ctx)) as test_client:
        yield test_client


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["encryption"] is True


def test_memory_store_retrieve_search_delete(client):
    stored = client.post(
        "/memory/store",
        json={
            "category": "personal",
            "content": "my ssh key fingerprint",
            "metadata": {"kind": "note"},
        },
    )
    assert stored.status_code == 200
    record_id = stored.json()["id"]

    fetched = client.get(f"/memory/retrieve/{record_id}")
    assert fetched.status_code == 200
    assert fetched.json()["content"] == "my ssh key fingerprint"

    hits = client.post("/memory/search", json={"query": "ssh"}).json()["results"]
    assert len(hits) == 1

    categories = client.get("/memory/categories").json()["categories"]
    assert categories["personal"] == 1

    deleted = client.delete(f"/memory/{record_id}")
    assert deleted.json() == {"id": record_id, "deleted": True}
    assert client.get(f"/memory/retrieve/{record_id}").status_code == 404


def test_memory_store_validation_error(client):
    response = client.post("/memory/store", json={"category": "bogus", "content": "x"})
    assert response.status_code == 400


def test_conversation_flow_with_llm(client, ctx):
    ctx.llm = FakeLLM()
    session_id = client.post("/conversation/start").json()["session_id"]
    response = client.post(f"/conversation/{session_id}/message", json={"content": "remember this"})
    assert response.status_code == 200
    assert response.json()["response"]["content"] == "echo: remember this"
    messages = client.get(f"/conversation/{session_id}/messages").json()["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant"]


def test_conversation_message_without_llm_is_502(client):
    session_id = client.post("/conversation/start").json()["session_id"]
    response = client.post(f"/conversation/{session_id}/message", json={"content": "hi"})
    assert response.status_code == 502  # LLMError -> 502
    assert "no LLM provider is configured" in response.json()["detail"]


def test_status_endpoint(client):
    client.post("/memory/store", json={"category": "ideas", "content": "note"})
    data = client.get("/status").json()
    assert data["mode"] == "passive"
    assert data["memory_records"] == 1


def test_bearer_token_required_when_configured(tmp_path, storage, secret_store):
    import asyncio

    from tests.conftest import make_settings

    from mysti.core.context import build_context

    settings = make_settings(tmp_path, api_token="s3cret")
    context = asyncio.run(
        build_context(settings=settings, storage=storage, secret_store=secret_store)
    )
    try:
        with TestClient(create_app(context)) as test_client:
            assert test_client.get("/status").status_code == 401
            assert (
                test_client.get("/status", headers={"Authorization": "Bearer wrong"}).status_code
                == 401
            )
            assert (
                test_client.get("/status", headers={"Authorization": "Bearer s3cret"}).status_code
                == 200
            )
            assert test_client.get("/health").status_code == 200  # health is open
    finally:
        asyncio.run(context.close())
