"""Application context: wires settings, storage, keys, cache, audit and services."""

import logging
from dataclasses import dataclass
from pathlib import Path

from mysti.core.llm import LLMClient, create_llm_client
from mysti.exceptions import MystiError
from mysti.memory.cache import BlobCache
from mysti.memory.conversations import ConversationStore
from mysti.memory.service import MemoryService
from mysti.security.audit import AuditLog
from mysti.security.keys import KeyManager
from mysti.security.keystore import SecretStore, create_secret_store
from mysti.settings import Settings
from mysti.storage.base import StorageBackend
from mysti.storage.local import LocalStorageBackend
from mysti.storage.s3 import S3StorageBackend

logger = logging.getLogger(__name__)


@dataclass
class AppContext:
    """Fully wired application object graph."""

    settings: Settings
    storage: StorageBackend
    keys: KeyManager
    cache: BlobCache
    audit: AuditLog
    memory: MemoryService
    conversations: ConversationStore
    llm: LLMClient
    first_run: bool = False

    async def close(self) -> None:
        """Release resources (HTTP connections)."""
        await self.llm.aclose()


async def build_context(
    settings: Settings | None = None,
    storage: StorageBackend | None = None,
    secret_store: SecretStore | None = None,
) -> AppContext:
    """Create and initialize the application context.

    Args:
        settings: Settings instance; loaded from the environment when None.
        storage: Storage backend override (used by tests).
        secret_store: Secret store override (used by tests).

    Raises:
        MystiError: On invalid configuration or failed initialization.
    """
    settings = settings or Settings()
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    if storage is None:
        if settings.storage_provider == "local":
            storage = LocalStorageBackend(Path(settings.data_dir) / "remote_storage")
        else:
            storage = S3StorageBackend(
                bucket=settings.storage_bucket,
                access_key=settings.storage_access_key,
                secret_key=settings.storage_secret_key,
                endpoint=settings.storage_endpoint,
                region=settings.storage_region,
            )
    secret_store = secret_store or create_secret_store(settings)
    keys = KeyManager(secret_store, storage)
    first_run = await keys.ensure_initialized()
    cache = BlobCache(max_bytes=settings.cache_max_bytes, ttl_seconds=settings.cache_ttl)
    audit = AuditLog(Path(settings.data_dir) / "audit.jsonl")
    memory = MemoryService(storage, keys, cache, audit, max_record_bytes=settings.max_record_bytes)
    conversations = ConversationStore(storage, keys, audit)
    context = AppContext(
        settings=settings,
        storage=storage,
        keys=keys,
        cache=cache,
        audit=audit,
        memory=memory,
        conversations=conversations,
        llm=create_llm_client(settings),
        first_run=first_run,
    )
    audit.log(
        "system.start",
        "app",
        metadata={"provider": settings.storage_provider, "first_run": first_run},
    )
    return context


__all__ = ["AppContext", "MystiError", "build_context"]
