"""Unit tests for the ciphertext-only RAM cache."""

from mysti.memory.cache import BlobCache


def test_put_get_hit_and_miss():
    cache = BlobCache(max_bytes=1024, ttl_seconds=60)
    assert cache.get("missing") is None
    cache.put("a", b"blob-a")
    assert cache.get("a") == b"blob-a"
    assert cache.get("missing") is None


def test_ttl_expiry():
    cache = BlobCache(max_bytes=1024, ttl_seconds=0.05)
    cache.put("a", b"blob-a")
    import time

    time.sleep(0.08)
    assert cache.get("a") is None


def test_lru_eviction_under_pressure():
    cache = BlobCache(max_bytes=240, ttl_seconds=60)
    cache.put("a", b"x" * 100)
    cache.put("b", b"y" * 100)
    cache.get("a")  # a becomes most recently used; b should evict first
    cache.put("c", b"z" * 100)
    assert cache.get("a") == b"x" * 100
    assert cache.get("b") is None
    assert cache.get("c") == b"z" * 100


def test_oversized_blob_is_not_cached():
    cache = BlobCache(max_bytes=10, ttl_seconds=60)
    cache.put("big", b"x" * 100)
    assert cache.get("big") is None


def test_delete_and_clear():
    cache = BlobCache(max_bytes=1024, ttl_seconds=60)
    cache.put("a", b"blob-a")
    cache.delete("a")
    assert cache.get("a") is None
    cache.put("b", b"blob-b")
    cache.clear()
    assert cache.stats()["entries"] == 0
    assert cache.stats()["bytes"] == 0


def test_stats():
    cache = BlobCache(max_bytes=1024, ttl_seconds=60)
    cache.put("a", b"x" * 50)
    stats = cache.stats()
    assert stats["entries"] == 1
    assert stats["bytes"] == 50
