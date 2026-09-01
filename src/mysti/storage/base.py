"""Abstract storage interface. Every provider sees ciphertext only."""

from abc import ABC, abstractmethod


class StorageBackend(ABC):
    """Object-storage abstraction used by all MYSTI persistence.

    Implementations never receive or return plaintext: the encryption layer
    seals data before it reaches a backend and opens it after retrieval.
    """

    @abstractmethod
    async def put(self, key: str, data: bytes) -> None:
        """Store ``data`` under ``key``."""

    @abstractmethod
    async def get(self, key: str) -> bytes:
        """Return the bytes stored under ``key``.

        Raises:
            RecordNotFoundError: If the key does not exist.
            StorageError: For any other backend failure.
        """

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete ``key`` if it exists; deleting a missing key is a no-op."""

    @abstractmethod
    async def list(self, prefix: str) -> list[str]:
        """Return all keys beginning with ``prefix``, sorted."""

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Return True if ``key`` exists."""
