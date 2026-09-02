import pathlib
import time

from mysti.settings import Settings
from mysti.memory.embeddings import EmbeddingService

settings = Settings(
    storage_provider="local",
    data_dir=pathlib.Path("."),
    secret_backend="memory",
    llm_provider="none",
    _env_file=None,
)
t0 = time.perf_counter()
emb = EmbeddingService.from_settings(settings)
print(f"embeddings: {time.perf_counter() - t0:.3f}s")

from mysti.research.connectors import (  # noqa: E402
    ArxivConnector,
    GitHubConnector,
    HackerNewsConnector,
    HuggingFaceConnector,
)
for cls in (GitHubConnector, ArxivConnector, HackerNewsConnector, HuggingFaceConnector):
    t0 = time.perf_counter()
    c = cls()
    print(f"{cls.__name__}: {time.perf_counter() - t0:.3f}s")

pathlib.Path("tmp_profile_out.txt").write_text("done\n")