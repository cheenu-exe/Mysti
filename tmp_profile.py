import asyncio
import pathlib
import tempfile
import time

from mysti.core.context import build_context
from mysti.security.keystore import InMemorySecretStore
from mysti.settings import Settings
from mysti.storage.local import LocalStorageBackend

settings = Settings(
    storage_provider="local",
    data_dir=pathlib.Path(tempfile.mkdtemp()),
    secret_backend="memory",
    llm_provider="none",
    _env_file=None,
)
storage = LocalStorageBackend(pathlib.Path(tempfile.mkdtemp()) / "remote")
secret_store = InMemorySecretStore()

t0 = time.perf_counter()
ctx = asyncio.run(build_context(settings=settings, storage=storage, secret_store=secret_store))
print(f"build_context: {time.perf_counter() - t0:.3f}s")
t0 = time.perf_counter()
asyncio.run(ctx.close())
print(f"close: {time.perf_counter() - t0:.3f}s")