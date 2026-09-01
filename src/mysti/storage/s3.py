"""S3-compatible remote storage backend (AWS S3, Backblaze B2, Cloudflare R2, MinIO)."""

from __future__ import annotations

import asyncio
import logging

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from mysti.exceptions import RecordNotFoundError, StorageError
from mysti.storage.base import StorageBackend

logger = logging.getLogger(__name__)

_NOT_FOUND_CODES = ("404", "NoSuchKey", "NotFound")
_StrList = list[str]


class S3StorageBackend(StorageBackend):
    """Object storage over any S3-compatible API. Receives ciphertext only."""

    def __init__(
        self,
        bucket: str,
        access_key: str | None = None,
        secret_key: str | None = None,
        endpoint: str | None = None,
        region: str | None = None,
    ) -> None:
        if not bucket:
            raise StorageError("s3 storage requires a bucket name")
        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            endpoint_url=endpoint,
            region_name=region or "us-east-1",
            config=Config(retries={"max_attempts": 5, "mode": "adaptive"}),
        )

    async def put(self, key: str, data: bytes) -> None:
        await asyncio.to_thread(self._put_sync, key, data)

    def _put_sync(self, key: str, data: bytes) -> None:
        try:
            self._client.put_object(Bucket=self._bucket, Key=key, Body=bytes(data))
        except ClientError as exc:
            raise StorageError(f"failed to upload object {key!r}: {exc}") from exc

    async def get(self, key: str) -> bytes:
        return await asyncio.to_thread(self._get_sync, key)

    def _get_sync(self, key: str) -> bytes:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            return response["Body"].read()
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in _NOT_FOUND_CODES:
                raise RecordNotFoundError(f"object not found: {key}") from exc
            raise StorageError(f"failed to download object {key!r}: {exc}") from exc

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self._delete_sync, key)

    def _delete_sync(self, key: str) -> None:
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
        except ClientError as exc:
            raise StorageError(f"failed to delete object {key!r}: {exc}") from exc

    async def list(self, prefix: str) -> list[str]:
        return await asyncio.to_thread(self._list_sync, prefix)

    def _list_sync(self, prefix: str) -> _StrList:
        keys: list[str] = []
        try:
            paginator = self._client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    keys.append(obj["Key"])
        except ClientError as exc:
            raise StorageError(f"failed to list objects with prefix {prefix!r}: {exc}") from exc
        return sorted(keys)

    async def exists(self, key: str) -> bool:
        return await asyncio.to_thread(self._exists_sync, key)

    def _exists_sync(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in _NOT_FOUND_CODES:
                return False
            raise StorageError(f"failed to check object {key!r}: {exc}") from exc
