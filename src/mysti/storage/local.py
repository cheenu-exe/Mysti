"""Local filesystem storage backend (development / testing).

Stores ciphertext only. Serves as the stand-in for remote object storage so
the full stack can run with zero paid services.
"""

from __future__ import annotations

from pathlib import Path

from mysti.exceptions import RecordNotFoundError, StorageError
from mysti.storage.base import StorageBackend


class LocalStorageBackend(StorageBackend):
    """Filesystem-backed object storage rooted at a directory."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        if not key or key.startswith(("/", "\\")) or "\\" in key or ".." in key or ":" in key:
            raise StorageError(f"invalid storage key: {key!r}")
        path = (self._root / key).resolve()
        if not str(path).startswith(str(self._root)):
            raise StorageError(f"invalid storage key: {key!r}")
        return path

    @staticmethod
    def _key(path: Path, root: Path) -> str:
        return path.relative_to(root).as_posix()

    async def put(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    async def get(self, key: str) -> bytes:
        path = self._path(key)
        if not path.is_file():
            raise RecordNotFoundError(f"object not found: {key}")
        return path.read_bytes()

    async def delete(self, key: str) -> None:
        path = self._path(key)
        path.unlink(missing_ok=True)

    async def list(self, prefix: str) -> list[str]:
        results: list[str] = []
        for path in self._root.rglob("*"):
            if path.is_file():
                key = self._key(path.resolve(), self._root)
                if key.startswith(prefix):
                    results.append(key)
        return sorted(results)

    async def exists(self, key: str) -> bool:
        return self._path(key).is_file()
