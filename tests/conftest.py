"""Shared fixtures: hermetic context with local storage and in-memory keystore."""

from pathlib import Path

import pytest

from mysti.core.context import AppContext, build_context
from mysti.memory.cache import BlobCache
from mysti.memory.conversations import ConversationStore
from mysti.memory.service import MemoryService
from mysti.security.audit import AuditLog
from mysti.security.keys import KeyManager
from mysti.security.keystore import InMemorySecretStore
from mysti.settings import Settings
from mysti.storage.local import LocalStorageBackend


def make_settings(tmp_path: Path, **overrides) -> Settings:
    """Hermetic settings: local storage, memory keystore, no LLM, no .env file."""
    defaults = dict(
        storage_provider="local",
        data_dir=tmp_path,
        secret_backend="memory",
        llm_provider="none",
        _env_file=None,
    )
    defaults.update(overrides)
    return Settings(**defaults)


@pytest.fixture
def storage(tmp_path: Path) -> LocalStorageBackend:
    return LocalStorageBackend(tmp_path / "remote_storage")


@pytest.fixture
def secret_store() -> InMemorySecretStore:
    return InMemorySecretStore()


@pytest.fixture
async def keys(storage: LocalStorageBackend, secret_store: InMemorySecretStore) -> KeyManager:
    manager = KeyManager(secret_store, storage)
    await manager.ensure_initialized()
    return manager


@pytest.fixture
def cache() -> BlobCache:
    return BlobCache(max_bytes=1024 * 1024, ttl_seconds=300)


@pytest.fixture
def audit(tmp_path: Path) -> AuditLog:
    return AuditLog(tmp_path / "audit.jsonl")


@pytest.fixture
async def memory(keys, storage, cache, audit) -> MemoryService:
    return MemoryService(storage, keys, cache, audit)


@pytest.fixture
async def conversations(keys, storage, audit) -> ConversationStore:
    return ConversationStore(storage, keys, audit)


@pytest.fixture
async def ctx(tmp_path: Path, storage, secret_store) -> AppContext:
    settings = make_settings(tmp_path)
    context = await build_context(settings=settings, storage=storage, secret_store=secret_store)
    yield context
    await context.close()
