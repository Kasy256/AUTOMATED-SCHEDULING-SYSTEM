import asyncio
import io
from typing import Protocol
from uuid import UUID

from minio import Minio

from cartlyf_api.settings import Settings


class ObjectStore(Protocol):
    async def put(self, key: str, data: bytes, content_type: str) -> None: ...

    async def get(self, key: str) -> bytes: ...


def org_object_key(organisation_id: UUID, *parts: str) -> str:
    return "/".join(("org", str(organisation_id), *parts))


def owned_by(key: str, organisation_id: UUID) -> bool:
    """Re-checked before every read: storage has no RLS, the key prefix is the tenant boundary."""
    return key.startswith(f"org/{organisation_id}/")


class S3ObjectStore:
    """S3 API (Cloudflare R2 in production, MinIO locally). The client is blocking, so calls
    run in a worker thread."""

    def __init__(self, settings: Settings) -> None:
        self._bucket = settings.s3_bucket
        self._client = Minio(
            settings.s3_endpoint,
            access_key=settings.s3_access_key.get_secret_value(),
            secret_key=settings.s3_secret_key.get_secret_value(),
            secure=settings.s3_secure,
            region=settings.s3_region,
        )

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        await asyncio.to_thread(
            self._client.put_object,
            self._bucket,
            key,
            io.BytesIO(data),
            len(data),
            content_type=content_type,
        )

    async def get(self, key: str) -> bytes:
        def read() -> bytes:
            response = self._client.get_object(self._bucket, key)
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()

        return await asyncio.to_thread(read)
