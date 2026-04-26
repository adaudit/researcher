"""S3-compatible object storage for raw artifacts and media.

Artifacts (HTML, screenshots, ad exports) and media (video, audio) are
stored here — never in Hindsight banks. Hindsight only holds strategic
knowledge derived from these artifacts.
"""

from __future__ import annotations

import hashlib
import logging
from io import BytesIO
from typing import Any

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

from app.core.config import settings

logger = logging.getLogger(__name__)


class ObjectStore:
    def __init__(self) -> None:
        self._client = None
        self._buckets_ready = False

    def _get_client(self):
        if self._client is None:
            self._client = boto3.client(
                "s3",
                endpoint_url=settings.S3_ENDPOINT_URL,
                aws_access_key_id=settings.S3_ACCESS_KEY,
                aws_secret_access_key=settings.S3_SECRET_KEY,
                region_name=settings.S3_REGION,
                config=BotoConfig(signature_version="s3v4"),
            )
        if not self._buckets_ready:
            self._ensure_buckets()
            self._buckets_ready = True
        return self._client

    def _ensure_buckets(self) -> None:
        for bucket in (settings.S3_BUCKET_ARTIFACTS, settings.S3_BUCKET_MEDIA):
            try:
                self._client.head_bucket(Bucket=bucket)
            except ClientError:
                try:
                    self._client.create_bucket(Bucket=bucket)
                    logger.info("s3.bucket_created bucket=%s", bucket)
                except ClientError:
                    logger.debug("s3.bucket_exists bucket=%s", bucket)

    def upload_artifact(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        content_hash = hashlib.sha256(data).hexdigest()
        extra: dict[str, Any] = {"ContentType": content_type}
        if metadata:
            extra["Metadata"] = metadata

        self._get_client().upload_fileobj(
            BytesIO(data),
            settings.S3_BUCKET_ARTIFACTS,
            key,
            ExtraArgs=extra,
        )
        logger.info("s3.artifact_uploaded key=%s size=%d", key, len(data))

        return {
            "bucket": settings.S3_BUCKET_ARTIFACTS,
            "key": key,
            "content_hash": content_hash,
            "size_bytes": len(data),
            "content_type": content_type,
        }

    def upload_media(
        self,
        key: str,
        data: bytes,
        content_type: str = "video/mp4",
    ) -> dict[str, Any]:
        content_hash = hashlib.sha256(data).hexdigest()
        self._get_client().upload_fileobj(
            BytesIO(data),
            settings.S3_BUCKET_MEDIA,
            key,
            ExtraArgs={"ContentType": content_type},
        )
        logger.info("s3.media_uploaded key=%s size=%d", key, len(data))

        return {
            "bucket": settings.S3_BUCKET_MEDIA,
            "key": key,
            "content_hash": content_hash,
            "size_bytes": len(data),
            "content_type": content_type,
        }

    async def download(self, bucket: str, key: str) -> bytes:
        buf = BytesIO()
        self._get_client().download_fileobj(bucket, key, buf)
        buf.seek(0)
        return buf.read()

    def get_presigned_url(
        self, bucket: str, key: str, expires_in: int = 3600
    ) -> str:
        return self._get_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires_in,
        )

    def delete(self, bucket: str, key: str) -> None:
        self._get_client().delete_object(Bucket=bucket, Key=key)


# Module-level singleton — no connection until first use
object_store = ObjectStore()
