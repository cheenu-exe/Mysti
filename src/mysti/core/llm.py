"""LLM abstraction for Phase 0 chat.

Direct HTTP clients (no provider SDKs) for OpenAI-compatible endpoints
(OpenAI, Ollama, any compatible proxy) and Anthropic. The default provider is
``none``: MYSTI's memory features work without any LLM configured, so no paid
service is required.
"""

import asyncio
import logging
from typing import Protocol

import httpx

from mysti.exceptions import LLMError, LLMNotConfiguredError
from mysti.settings import Settings

logger = logging.getLogger(__name__)

DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-haiku-latest",
    "ollama": "llama3.1",
}
_MAX_RETRIES = 2
_BACKOFF_SECONDS = 1.0


class LLMClient(Protocol):
    """Protocol implemented by all LLM providers."""

    async def complete(self, messages: list[dict[str, str]], model: str | None = None) -> str:
        """Send chat messages and return the assistant's reply text."""
        ...

    async def aclose(self) -> None:
        """Release underlying HTTP resources."""
        ...


class UnconfiguredLLM:
    """Placeholder used when no provider is configured; raises on use."""

    async def complete(self, messages: list[dict[str, str]], model: str | None = None) -> str:
        raise LLMNotConfiguredError(
            "no LLM provider is configured; set MYSTI_LLM_PROVIDER and MYSTI_LLM_API_KEY"
        )

    async def aclose(self) -> None:
        return None


class _HttpLLMClient:
    """Shared retry/error handling for HTTP-based providers."""

    def __init__(self, client: httpx.AsyncClient, model: str, endpoint: str) -> None:
        self._client = client
        self._model = model
        self._endpoint = endpoint

    async def complete(self, messages: list[dict[str, str]], model: str | None = None) -> str:
        payload = self._build_payload(messages, model or self._model)
        last_error: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                response = await self._client.post(self._endpoint, json=payload)
                if response.status_code >= 500 or response.status_code == 429:
                    raise LLMError(f"LLM provider returned status {response.status_code}")
                response.raise_for_status()
                return self._extract(response.json())
            except (httpx.HTTPError, LLMError) as exc:
                last_error = exc
                logger.warning("LLM request attempt %d failed: %s", attempt + 1, exc)
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(_BACKOFF_SECONDS * (2**attempt))
        raise LLMError(f"LLM request failed after retries: {last_error}") from last_error

    def _build_payload(self, messages: list[dict[str, str]], model: str) -> dict:
        raise NotImplementedError

    def _extract(self, data: dict) -> str:
        raise NotImplementedError

    async def aclose(self) -> None:
        await self._client.aclose()


class OpenAICompatibleClient(_HttpLLMClient):
    """OpenAI chat-completions client (also used for Ollama and proxies)."""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60.0,
            transport=transport,
        )
        super().__init__(client, model, "/chat/completions")

    def _build_payload(self, messages: list[dict[str, str]], model: str) -> dict:
        return {"model": model, "messages": messages}

    def _extract(self, data: dict) -> str:
        try:
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("unexpected LLM response format") from exc


class AnthropicClient(_HttpLLMClient):
    """Anthropic Messages API client."""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://api.anthropic.com",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
            timeout=60.0,
            transport=transport,
        )
        super().__init__(client, model, "/v1/messages")

    def _build_payload(self, messages: list[dict[str, str]], model: str) -> dict:
        system = "\n".join(m["content"] for m in messages if m["role"] == "system")
        chat = [m for m in messages if m["role"] != "system"]
        payload: dict = {"model": model, "max_tokens": 1024, "messages": chat}
        if system:
            payload["system"] = system
        return payload

    def _extract(self, data: dict) -> str:
        try:
            return "".join(block.get("text", "") for block in data["content"])
        except (KeyError, TypeError) as exc:
            raise LLMError("unexpected LLM response format") from exc


def create_llm_client(settings: Settings) -> LLMClient:
    """Build the LLM client configured by settings (never raises for 'none')."""
    provider = settings.llm_provider
    if provider == "none":
        return UnconfiguredLLM()
    model = settings.llm_model or DEFAULT_MODELS[provider]
    if provider == "openai":
        if not settings.llm_api_key:
            return UnconfiguredLLM()
        return OpenAICompatibleClient(
            settings.llm_api_key,
            model,
            base_url=settings.llm_base_url or "https://api.openai.com/v1",
        )
    if provider == "anthropic":
        if not settings.llm_api_key:
            return UnconfiguredLLM()
        return AnthropicClient(
            settings.llm_api_key,
            model,
            base_url=settings.llm_base_url or "https://api.anthropic.com",
        )
    # ollama: local server, no API key needed
    return OpenAICompatibleClient(
        api_key="ollama",
        model=model,
        base_url=settings.llm_base_url or "http://localhost:11434/v1",
    )
