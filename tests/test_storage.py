"""Storage backend tests: local filesystem and mocked S3."""

import pytest

from mysti.exceptions import RecordNotFoundError, StorageError
from mysti.storage.local import LocalStorageBackend
from mysti.storage.s3 import S3StorageBackend

SAMPLE = b"\x01\x02ciphertext-blob-\xff"


async def exercise_backend(backend) -> None:
    assert await backend.exists("a/b.enc") is False
    await backend.put("a/b.enc", SAMPLE)
    assert await backend.exists("a/b.enc") is True
    assert await backend.get("a/b.enc") == SAMPLE
    await backend.put("a/c.enc", b"other")
    assert await backend.list("a/") == ["a/b.enc", "a/c.enc"]
    await backend.delete("a/b.enc")
    assert await backend.exists("a/b.enc") is False
    with pytest.raises(RecordNotFoundError):
        await backend.get("a/b.enc")
    await backend.delete("a/b.enc")  # idempotent


async def test_local_backend_roundtrip(tmp_path):
    await exercise_backend(LocalStorageBackend(tmp_path / "remote"))


async def test_local_backend_rejects_traversal(tmp_path):
    backend = LocalStorageBackend(tmp_path / "remote")
    for bad_key in ("../evil.enc", "..\\evil.enc", "C:/evil.enc", "/abs.enc", "a/../b.enc"):
        with pytest.raises(StorageError):
            await backend.get(bad_key)


async def test_local_backend_get_missing(tmp_path):
    backend = LocalStorageBackend(tmp_path / "remote")
    with pytest.raises(RecordNotFoundError):
        await backend.get("nope.enc")


@pytest.fixture
def s3_backend():
    from moto import mock_aws

    with mock_aws():
        import boto3

        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="mysti-test")
        yield S3StorageBackend(
            bucket="mysti-test",
            access_key="testing",
            secret_key="testing",
            region="us-east-1",
        )


async def test_s3_backend_roundtrip(s3_backend):
    await exercise_backend(s3_backend)


async def test_s3_backend_get_missing(s3_backend):
    with pytest.raises(RecordNotFoundError):
        await s3_backend.get("does/not/exist.enc")


def test_s3_backend_requires_bucket():
    with pytest.raises(StorageError):
        S3StorageBackend(bucket="")
