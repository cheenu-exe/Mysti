"""Key hierarchy: master key (OS keystore) -> category keys -> per-record keys.

The master key never leaves the device and is never uploaded. The category-key
manifest (wrapped category keys) lives in remote storage, sealed with the
master key. Category keys are versioned so rotation retains old decryption
keys; per-record data keys are wrapped inside each record's envelope.
"""

import base64
import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from mysti.exceptions import EncryptionError, KeyManagementError
from mysti.security.keystore import SecretStore
from mysti.storage.base import StorageBackend

logger = logging.getLogger(__name__)

DEFAULT_MEMORY_CATEGORIES = (
    "personal",
    "projects",
    "relationships",
    "technical",
    "research",
    "ideas",
)
RESERVED_CATEGORIES = ("meta", "conversation")
VALID_CATEGORY_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789-")
MANIFEST_KEY = "mysti/metadata/categories.enc"
MANIFEST_AAD = b"mysti:categories-manifest"
_NONCE_SIZE = 12


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


def generate_key() -> bytes:
    """Generate a random 256-bit key."""
    return os.urandom(32)


def _aad(*parts: str) -> bytes:
    return ":".join(parts).encode("utf-8")


def _encrypt_manifest(master_key: bytes, plaintext: bytes) -> bytes:
    nonce = os.urandom(_NONCE_SIZE)
    return nonce + AESGCM(master_key).encrypt(nonce, plaintext, MANIFEST_AAD)


def _decrypt_manifest(master_key: bytes, blob: bytes) -> bytes:
    nonce, ciphertext = blob[:_NONCE_SIZE], blob[_NONCE_SIZE:]
    try:
        return AESGCM(master_key).decrypt(nonce, ciphertext, MANIFEST_AAD)
    except InvalidTag as exc:
        raise EncryptionError("category-key manifest failed authentication") from exc


class KeyManager:
    """Manages the master key and wrapped, versioned category keys."""

    def __init__(self, secret_store: SecretStore, storage: StorageBackend) -> None:
        self._store = secret_store
        self._storage = storage
        self._master: bytes | None = None

    async def get_master_key(self) -> bytes:
        """Return the master key from the OS keystore.

        Raises:
            KeyManagementError: If no master key exists (run first-run setup).
        """
        if self._master is None:
            master = self._store.get()
            if master is None:
                raise KeyManagementError(
                    "master key not found in the OS keystore; run `mysti init` first"
                )
            self._master = master
        return self._master

    async def has_master_key(self) -> bool:
        return self._store.get() is not None

    async def ensure_initialized(
        self, categories: tuple[str, ...] = DEFAULT_MEMORY_CATEGORIES
    ) -> bool:
        """First-run setup: create the master key and the category-key manifest.

        Returns:
            True if this call created the key material (i.e. this was a first run).
        """
        created = False
        if self._store.get() is None:
            self._store.set(generate_key())
            self._master = None
            created = True
        if not await self._storage.exists(MANIFEST_KEY):
            await self.get_master_key()
            manifest: dict[str, Any] = {"version": 1, "categories": {}}
            for name in (*categories, *RESERVED_CATEGORIES):
                manifest["categories"][name] = self._new_category_entry(name)
            await self._save_manifest(manifest)
            logger.info(
                "Created key hierarchy with categories: %s", ", ".join(manifest["categories"])
            )
        return created

    # --- manifest helpers (continued below) ---

    async def _load_manifest(self) -> dict:
        blob = await self._storage.get(MANIFEST_KEY)
        data = _decrypt_manifest(await self.get_master_key(), blob)
        return json.loads(data)

    async def _save_manifest(self, manifest: dict) -> None:
        blob = _encrypt_manifest(await self.get_master_key(), json.dumps(manifest).encode("utf-8"))
        await self._storage.put(MANIFEST_KEY, blob)

    def _new_category_entry(self, category: str) -> dict:
        key = generate_key()
        wrapped = self._wrap(category, 1, key)
        return {
            "active": 1,
            "keys": [{"version": 1, "wrapped": wrapped, "created_at": _iso_now()}],
        }

    def _wrap(self, category: str, version: int, key: bytes) -> str:
        master = self._master if self._master is not None else self._store.get()
        if master is None:
            raise KeyManagementError("master key is missing")
        nonce = os.urandom(_NONCE_SIZE)
        ciphertext = AESGCM(master).encrypt(nonce, key, _aad("mysti:cat", category, f"v{version}"))
        return base64.b64encode(nonce + ciphertext).decode("ascii")

    def _unwrap(self, category: str, version: int, wrapped: str) -> bytes:
        master = self._master if self._master is not None else self._store.get()
        if master is None:
            raise KeyManagementError("master key is missing")
        blob = base64.b64decode(wrapped)
        nonce, ciphertext = blob[:_NONCE_SIZE], blob[_NONCE_SIZE:]
        try:
            return AESGCM(master).decrypt(
                nonce, ciphertext, _aad("mysti:cat", category, f"v{version}")
            )
        except InvalidTag as exc:
            raise KeyManagementError(
                f"failed to unwrap key for category {category!r} "
                "(master key changed or manifest was tampered with)"
            ) from exc

    # --- public key operations (continued below) ---

    async def category_names(self) -> list[str]:
        manifest = await self._load_manifest()
        return sorted(manifest["categories"])

    async def create_category(self, category: str) -> None:
        """Add a new category to the manifest with a fresh wrapped key.

        Raises:
            KeyManagementError: If the name is invalid or already exists.
        """
        if (
            not category
            or category != category.strip()
            or not set(category) <= VALID_CATEGORY_CHARS
        ):
            raise KeyManagementError(
                f"invalid category name: {category!r} (use lowercase letters, digits, '-')"
            )
        if category in RESERVED_CATEGORIES:
            raise KeyManagementError(f"category {category!r} is reserved")
        manifest = await self._load_manifest()
        if category in manifest["categories"]:
            raise KeyManagementError(f"category already exists: {category!r}")
        manifest["categories"][category] = self._new_category_entry(category)
        await self._save_manifest(manifest)
        logger.info("Created category %r with a fresh wrapped key", category)

    async def get_category_key(
        self, category: str, version: int | None = None
    ) -> tuple[bytes, int]:
        """Return the (key, version) for a category.

        Args:
            category: Category name.
            version: Specific key version; None returns the active version.

        Raises:
            KeyManagementError: If the category or version is unknown.
        """
        manifest = await self._load_manifest()
        entry = manifest["categories"].get(category)
        if entry is None:
            raise KeyManagementError(f"unknown category: {category!r}")
        target = version if version is not None else entry["active"]
        for key_entry in entry["keys"]:
            if key_entry["version"] == target:
                return self._unwrap(category, target, key_entry["wrapped"]), target
        raise KeyManagementError(f"category {category!r} has no key version {target}")

    async def active_category_version(self, category: str) -> int:
        """Return the active key version for ``category``."""
        manifest = await self._load_manifest()
        entry = manifest["categories"].get(category)
        if entry is None:
            raise KeyManagementError(f"unknown category: {category!r}")
        return entry["active"]

    async def rotate_category_key(self, category: str) -> int:
        """Create a new key version for ``category`` and make it active.

        Old versions are retained so previously written records remain
        readable. Re-encrypting existing records is left to callers.
        Returns the new active version.
        """
        manifest = await self._load_manifest()
        entry = manifest["categories"].get(category)
        if entry is None:
            raise KeyManagementError(f"unknown category: {category!r}")
        new_version = entry["active"] + 1
        entry["keys"].append(
            {
                "version": new_version,
                "wrapped": self._wrap(category, new_version, generate_key()),
                "created_at": _iso_now(),
            }
        )
        entry["active"] = new_version
        await self._save_manifest(manifest)
        logger.info("Rotated key for category %r to version %d", category, new_version)
        return new_version
