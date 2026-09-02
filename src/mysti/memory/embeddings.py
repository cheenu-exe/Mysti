"""Embedding service: local model first, API fallback, offline hashing fallback.

Backends are tried in order; the first that produces vectors wins. The default
local model is ``all-MiniLM-L6-v2`` (384 dimensions, ~80 MB, downloaded once
into ``~/.cache/mysti/embeddings/``). Because sentence-transformers pulls in
torch, it ships as the optional ``mysti[embeddings]`` extra; without it MYSTI
degrades to API embeddings (when a key is configured) and finally to a
deterministic offline embedder so semantic features always work.

Computed embeddings are cached in RAM (LRU, bounded) keyed by content digest.
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import logging
import math
import re
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Protocol

import httpx
import numpy as np

from mysti.exceptions import MystiError
from mysti.settings import Settings

logger = logging.getLogger(__name__)

EMBEDDING_DIMENSIONS = 384
DEFAULT_MODEL = "all-MiniLM-L6-v2"
MODEL_CACHE_DIR = Path.home() / ".cache" / "mysti" / "embeddings"


class EmbeddingBackend(Protocol):
    """A provider of dense vectors for text."""

    name: str

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per text."""
        ...

    async def aclose(self) -> None:
        """Release underlying resources."""
        ...


class HashingEmbeddingBackend:
    """Deterministic offline embedder: a bag of hashed tokens.

    Not a semantic model — it only scores token overlap — but it is instant,
    needs no downloads and keeps search/consolidation functional everywhere.
    Vectors are non-negative, so texts sharing no tokens score exactly 0.0.
    """

    name = "hashing"

    def __init__(self, dimensions: int = EMBEDDING_DIMENSIONS) -> None:
        self._dimensions = dimensions

    async def embed(self, texts: list[str]) -> list[list[float]]:  # noqa: RUF029
        return [self._vectorize(text) for text in texts]

    def _vectorize(self, text: str) -> list[float]:
        vector = [0.0] * self._dimensions
        for token in re.findall(r"[a-z0-9]+", text.lower()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:8], "big") % self._dimensions
            vector[index] += 1.0
        norm = math.sqrt(sum(value * value for value in vector))
        if norm:
            vector = [value / norm for value in vector]
        return vector

    async def aclose(self) -> None:
        return None


class SentenceTransformerBackend:
    """Local sentence-transformers model (downloads on first use)."""

    name = "sentence-transformers"

    def __init__(self, model_name: str = DEFAULT_MODEL, cache_dir: Path = MODEL_CACHE_DIR) -> None:
        self._model_name = model_name
        self._cache_dir = cache_dir
        self._model = None

    def _ensure_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:  # pragma: no cover - depends on env
                raise MystiError(
                    "sentence-transformers is not installed; "
                    "run `pip install 'mysti[embeddings]'` to use the local model"
                ) from exc
            logger.info(
                "Loading embedding model %r (cached in %s)", self._model_name, self._cache_dir
            )
            self._model = SentenceTransformer(self._model_name, cache_folder=str(self._cache_dir))
        return self._model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        model = self._ensure_model()
        vectors = await asyncio.to_thread(
            lambda: model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        )
        return [vector.tolist() for vector in vectors]

    async def aclose(self) -> None:
        self._model = None


class APIEmbeddingBackend:
    """OpenAI-compatible ``/embeddings`` endpoint fallback."""

    name = "api"

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "text-embedding-3-small",
        dimensions: int = EMBEDDING_DIMENSIONS,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._model = model
        self._dimensions = dimensions
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60.0,
            transport=transport,
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        response = await self._client.post(
            "/embeddings",
            json={"model": self._model, "input": texts, "dimensions": self._dimensions},
        )
        response.raise_for_status()
        data = response.json()
        try:
            return [item["embedding"] for item in sorted(data["data"], key=lambda i: i["index"])]
        except (KeyError, IndexError, TypeError) as exc:
            raise MystiError("unexpected embedding API response format") from exc

    async def aclose(self) -> None:
        await self._client.aclose()


def cosine_similarity(a: list[float] | None, b: list[float] | None) -> float:
    """Cosine similarity between two vectors (0.0 when either is missing)."""
    if not a or not b or len(a) != len(b):
        return 0.0
    va, vb = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    denominator = float(np.linalg.norm(va) * np.linalg.norm(vb))
    if not denominator:
        return 0.0
    similarity = float(np.dot(va, vb) / denominator)
    return max(-1.0, min(1.0, similarity))


class EmbeddingService:
    """Generates, caches and compares text embeddings across a backend chain."""

    def __init__(
        self,
        backends: list[EmbeddingBackend],
        *,
        dimensions: int = EMBEDDING_DIMENSIONS,
        cache_size: int = 2048,
    ) -> None:
        if not backends:
            raise MystiError("EmbeddingService requires at least one backend")
        self._backends = backends
        self._dimensions = dimensions
        self._cache_size = cache_size
        self._cache: OrderedDict[str, list[float]] = OrderedDict()
        self._lock = threading.Lock()

    @classmethod
    def from_settings(cls, settings: Settings) -> EmbeddingService | None:
        """Build a service from settings; None when embeddings are disabled."""
        provider = settings.embedding_provider
        if provider == "none":
            return None
        backends: list[EmbeddingBackend] = []
        if provider in ("auto", "sentence-transformers"):
            if importlib.util.find_spec("sentence_transformers") is not None:
                backends.append(SentenceTransformerBackend(settings.embedding_model))
            elif provider == "sentence-transformers":
                raise MystiError(
                    "MYSTI_EMBEDDING_PROVIDER=sentence-transformers but the package "
                    "is not installed; run `pip install 'mysti[embeddings]'`"
                )
        if provider in ("auto", "api") and settings.embedding_api_key:
            backends.append(
                APIEmbeddingBackend(
                    settings.embedding_api_key,
                    settings.embedding_api_base,
                    dimensions=settings.embedding_dimensions,
                )
            )
        elif provider == "api":
            raise MystiError("MYSTI_EMBEDDING_PROVIDER=api requires MYSTI_EMBEDDING_API_KEY")
        if provider == "hashing" or not backends:
            backends.append(HashingEmbeddingBackend(settings.embedding_dimensions))
        return cls(
            backends,
            dimensions=settings.embedding_dimensions,
            cache_size=settings.embedding_cache_size,
        )

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @property
    def backend_name(self) -> str:
        """Name of the backend that will serve the next request."""
        return self._backends[0].name

    def _cache_get(self, text: str) -> list[float] | None:
        key = hashlib.sha256(text.encode("utf-8")).hexdigest()
        with self._lock:
            vector = self._cache.get(key)
            if vector is not None:
                self._cache.move_to_end(key)
            return vector

    def _cache_put(self, text: str, vector: list[float]) -> None:
        key = hashlib.sha256(text.encode("utf-8")).hexdigest()
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = vector
            while len(self._cache) > self._cache_size:
                self._cache.popitem(last=False)

    async def _embed(self, texts: list[str]) -> list[list[float]]:
        last_error: Exception | None = None
        for index, backend in enumerate(self._backends):
            try:
                return await backend.embed(texts)
            except MystiError:
                raise
            except Exception as exc:  # noqa: BLE001 - fall through to next backend
                last_error = exc
                logger.warning("embedding backend %r failed: %s", backend.name, exc)
                if index + 1 < len(self._backends):
                    logger.warning(
                        "falling back to embedding backend %r", self._backends[index + 1].name
                    )
        raise MystiError(f"all embedding backends failed: {last_error}") from last_error

    async def generate_embedding(self, text: str) -> list[float]:
        """Return the embedding for ``text`` (RAM-cached)."""
        if not text.strip():
            return []
        cached = self._cache_get(text)
        if cached is not None:
            return cached
        (vector,) = await self._embed([text])
        self._cache_put(text, vector)
        return vector

    async def generate_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """Return embeddings for many texts, computing cache misses in one call."""
        results: list[list[float] | None] = [self._cache_get(text) for text in texts]
        missing = [i for i, vector in enumerate(results) if vector is None]
        if missing:
            vectors = await self._embed([texts[i] for i in missing])
            for i, vector in zip(missing, vectors, strict=True):
                self._cache_put(texts[i], vector)
                results[i] = vector
        return [vector for vector in results if vector is not None]

    @staticmethod
    def similarity_score(a: list[float], b: list[float]) -> float:
        """Cosine similarity in [-1, 1] between two embeddings."""
        return cosine_similarity(a, b)

    async def aclose(self) -> None:
        for backend in self._backends:
            await backend.aclose()
