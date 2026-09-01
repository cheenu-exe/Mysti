"""Unit tests for the key hierarchy and keystore backends."""

import pytest

from mysti.exceptions import KeyManagementError
from mysti.security import keys as keys_module
from mysti.security.keys import (
    DEFAULT_MEMORY_CATEGORIES,
    MANIFEST_KEY,
    RESERVED_CATEGORIES,
    KeyManager,
)
from mysti.security.keystore import InMemorySecretStore


async def test_ensure_initialized_creates_key_material(keys: KeyManager):
    assert await keys.has_master_key()
    names = await keys.category_names()
    for category in (*DEFAULT_MEMORY_CATEGORIES, *RESERVED_CATEGORIES):
        assert category in names


async def test_ensure_initialized_is_idempotent(storage, secret_store):
    first = KeyManager(secret_store, storage)
    assert await first.ensure_initialized() is True
    assert await first.ensure_initialized() is False


async def test_category_keys_are_stable_and_distinct(keys: KeyManager):
    personal_a, version_a = await keys.get_category_key("personal")
    personal_b, _ = await keys.get_category_key("personal")
    projects, version_b = await keys.get_category_key("projects")
    assert personal_a == personal_b
    assert personal_a != projects
    assert version_a == 1 and version_b == 1


async def test_unknown_category_raises(keys: KeyManager):
    with pytest.raises(KeyManagementError):
        await keys.get_category_key("does-not-exist")


async def test_rotate_category_key_retains_old_version(keys: KeyManager):
    old_key, old_version = await keys.get_category_key("personal")
    new_version = await keys.rotate_category_key("personal")
    assert new_version == old_version + 1
    new_key, _ = await keys.get_category_key("personal")
    assert new_key != old_key
    historical, _ = await keys.get_category_key("personal", old_version)
    assert historical == old_key


async def test_master_key_never_uploaded(storage, secret_store, keys: KeyManager):
    master = await keys.get_master_key()
    for key in await storage.list(""):
        assert master not in await storage.get(key), f"master key leaked into {key}"


async def test_manifest_is_encrypted(storage, secret_store, keys: KeyManager):
    blob = await storage.get(MANIFEST_KEY)
    assert b"personal" not in blob
    assert b"categories" not in blob


async def test_keys_survive_manager_reload(storage, secret_store):
    first = KeyManager(secret_store, storage)
    await first.ensure_initialized()
    original, version = await first.get_category_key("projects")

    second = KeyManager(secret_store, storage)
    reloaded, reloaded_version = await second.get_category_key("projects")
    assert reloaded == original
    assert reloaded_version == version


def test_wrap_binds_identity():
    store = InMemorySecretStore()
    store.set(keys_module.generate_key())
    manager = KeyManager(store, None)  # storage unused by wrap/unwrap
    key = keys_module.generate_key()
    wrapped = manager._wrap("personal", 1, key)
    assert manager._unwrap("personal", 1, wrapped) == key
    with pytest.raises(KeyManagementError):
        manager._unwrap("projects", 1, wrapped)
