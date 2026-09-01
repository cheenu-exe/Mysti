"""LLM client tests using mocked HTTP transports (no network, no paid services)."""

import httpx
import pytest

from mysti.core.llm import (
    AnthropicClient,
    OpenAICompatibleClient,
    UnconfiguredLLM,
    create_llm_client,
)
from mysti.exceptions import LLMError, LLMNotConfiguredError
from mysti.settings import Settings


def _openai_handler(recorder):
    def handler(request: httpx.Request) -> httpx.Response:
        recorder.append(request)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "hello from the mock"}}]},
        )

    return handler


async def test_openai_client_sends_messages_and_parses_reply():
    calls: list[httpx.Request] = []
    client = OpenAICompatibleClient(
        api_key="test-key",
        model="test-model",
        base_url="https://mock.example/v1",
        transport=httpx.MockTransport(_openai_handler(calls)),
    )
    reply = await client.complete(
        [{"role": "user", "content": "hi"}],
    )
    await client.aclose()
    assert reply == "hello from the mock"
    body = calls[0].headers
    assert body["Authorization"] == "Bearer test-key"


def _retry_handler(counter):
    def handler(request: httpx.Request) -> httpx.Response:
        counter.append(1)
        if len(counter) < 3:
            return httpx.Response(500, json={"error": "boom"})
        return httpx.Response(200, json={"choices": [{"message": {"content": "recovered"}}]})

    return handler


async def test_openai_client_retries_on_5xx():
    counter: list[int] = []
    client = OpenAICompatibleClient(
        api_key="k", model="m", transport=httpx.MockTransport(_retry_handler(counter))
    )
    reply = await client.complete([{"role": "user", "content": "hi"}])
    await client.aclose()
    assert reply == "recovered"
    assert len(counter) == 3


def _persistent_failure_handler(counter):
    def handler(request: httpx.Request) -> httpx.Response:
        counter.append(1)
        return httpx.Response(500, json={"error": "down"})

    return handler


async def test_openai_client_raises_after_retries():
    counter: list[int] = []
    client = OpenAICompatibleClient(
        api_key="k", model="m", transport=httpx.MockTransport(_persistent_failure_handler(counter))
    )
    with pytest.raises(LLMError):
        await client.complete([{"role": "user", "content": "hi"}])
    await client.aclose()
    assert len(counter) == 3  # initial + 2 retries


async def test_anthropic_client_maps_system_and_parses_content():
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            200,
            json={"content": [{"type": "text", "text": "anthropic reply"}]},
        )

    client = AnthropicClient(
        api_key="sk-test",
        model="claude-test",
        base_url="https://mock.example",
        transport=httpx.MockTransport(handler),
    )
    reply = await client.complete(
        [
            {"role": "system", "content": "be terse"},
            {"role": "user", "content": "hi"},
        ]
    )
    await client.aclose()
    assert reply == "anthropic reply"
    import json

    payload = json.loads(calls[0].content)
    assert payload["system"] == "be terse"
    assert payload["max_tokens"] == 1024


def test_create_llm_client_none_provider():
    settings = Settings(llm_provider="none", _env_file=None)
    assert isinstance(create_llm_client(settings), UnconfiguredLLM)


def test_create_llm_client_openai_without_key():
    settings = Settings(llm_provider="openai", llm_api_key="", _env_file=None)
    assert isinstance(create_llm_client(settings), UnconfiguredLLM)


def test_unconfigured_llm_raises():
    async def check():
        with pytest.raises(LLMNotConfiguredError):
            await UnconfiguredLLM().complete([])

    import asyncio

    asyncio.run(check())
