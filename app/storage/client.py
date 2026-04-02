from __future__ import annotations

import os
from typing import Dict, Protocol, runtime_checkable


@runtime_checkable
class StorageClientProtocol(Protocol):
    def get_presigned_upload_url(
        self, object_key: str, expires_in_seconds: int
    ) -> str: ...

    def get_presigned_download_url(
        self, object_key: str, expires_in_seconds: int
    ) -> str: ...

    def delete_object(self, object_key: str) -> None: ...

    def get_object_bytes(self, object_key: str) -> bytes: ...

    def put_object_bytes(self, object_key: str, data: bytes, content_type: str = "application/epub+zip") -> None: ...


class BotoStorageClient:
    """boto3-backed S3-compatible storage client.

    Configured from environment:
      S3_BUCKET_NAME        — required
      S3_ENDPOINT_URL       — optional (for non-AWS S3-compatible providers)
      AWS_ACCESS_KEY_ID     — required
      AWS_SECRET_ACCESS_KEY — required
      AWS_REGION            — optional, default 'us-east-1'
    """

    def __init__(self) -> None:
        import boto3

        self._bucket = os.environ["S3_BUCKET_NAME"]
        endpoint_url = os.environ.get("S3_ENDPOINT_URL") or None
        region = os.environ.get("AWS_REGION", "us-east-1")

        self._client = boto3.client(
            "s3",
            region_name=region,
            endpoint_url=endpoint_url,
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        )

    def get_presigned_upload_url(
        self, object_key: str, expires_in_seconds: int
    ) -> str:
        return self._client.generate_presigned_url(
            "put_object",
            Params={"Bucket": self._bucket, "Key": object_key},
            ExpiresIn=expires_in_seconds,
        )

    def get_presigned_download_url(
        self, object_key: str, expires_in_seconds: int
    ) -> str:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": object_key},
            ExpiresIn=expires_in_seconds,
        )

    def delete_object(self, object_key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=object_key)

    def get_object_bytes(self, object_key: str) -> bytes:
        response = self._client.get_object(Bucket=self._bucket, Key=object_key)
        return response["Body"].read()

    def put_object_bytes(self, object_key: str, data: bytes, content_type: str = "application/epub+zip") -> None:
        self._client.put_object(
            Bucket=self._bucket,
            Key=object_key,
            Body=data,
            ContentType=content_type,
        )


class FakeStorageClient:
    """In-memory storage client for tests. No real S3 calls."""

    def __init__(self) -> None:
        self._store: Dict[str, bytes] = {}

    def put_object(self, object_key: str, data: bytes) -> None:
        """Store bytes — test helper, not part of protocol."""
        self._store[object_key] = data

    def get_presigned_upload_url(
        self, object_key: str, expires_in_seconds: int
    ) -> str:
        return f"https://fake-s3.example.com/upload/{object_key}?expires={expires_in_seconds}"

    def get_presigned_download_url(
        self, object_key: str, expires_in_seconds: int
    ) -> str:
        return f"https://fake-s3.example.com/download/{object_key}?expires={expires_in_seconds}"

    def delete_object(self, object_key: str) -> None:
        self._store.pop(object_key, None)

    def get_object_bytes(self, object_key: str) -> bytes:
        if object_key not in self._store:
            raise KeyError(f"Object not found in fake storage: {object_key}")
        return self._store[object_key]

    def put_object_bytes(self, object_key: str, data: bytes, content_type: str = "application/epub+zip") -> None:
        self._store[object_key] = data


def get_storage_client() -> StorageClientProtocol:
    """FastAPI dependency. Override via app.dependency_overrides in tests."""
    return BotoStorageClient()
