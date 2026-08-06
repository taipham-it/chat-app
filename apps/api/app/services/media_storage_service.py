import io
import uuid
from pathlib import Path

from anyio import to_thread
from minio import Minio
from minio.error import S3Error

from app.core.config import get_settings


class MediaStorageService:
    def __init__(self) -> None:
        settings = get_settings()
        self.bucket = settings.MINIO_BUCKET
        self.client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )

    def _ensure_bucket(self) -> None:
        if self.client.bucket_exists(self.bucket):
            return
        try:
            self.client.make_bucket(self.bucket)
        except S3Error as exc:
            if exc.code not in {"BucketAlreadyExists", "BucketAlreadyOwnedByYou"}:
                raise

    async def upload(
        self,
        *,
        conversation_id: uuid.UUID,
        filename: str,
        content_type: str,
        data: bytes,
    ) -> str:
        safe_suffix = Path(filename).suffix.lower()[:16]
        object_key = f"conversations/{conversation_id}/{uuid.uuid4()}{safe_suffix}"

        def put() -> None:
            self._ensure_bucket()
            self.client.put_object(
                self.bucket,
                object_key,
                io.BytesIO(data),
                length=len(data),
                content_type=content_type,
            )

        await to_thread.run_sync(put)
        return object_key

    async def delete(self, object_key: str) -> None:
        await to_thread.run_sync(self.client.remove_object, self.bucket, object_key)

    async def get(self, object_key: str):
        return await to_thread.run_sync(self.client.get_object, self.bucket, object_key)
