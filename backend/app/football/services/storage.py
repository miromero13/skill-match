from __future__ import annotations

import hashlib
import hmac
import logging
import time
from pathlib import Path
from typing import Any

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import BASE_DIR, settings
from app.football.config import load_football_config

logger = logging.getLogger("skillmatch.football.storage")


class GarageS3StorageService:
    """
    S3-compatible object storage client configured for self-hosted Garage S3 on Coolify.
    Provides automatic local-filesystem fallback when S3 credentials/endpoint are offline
    in local development or automated tests.
    """

    def __init__(
        self,
        endpoint_url: str | None = None,
        region_name: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        bucket_name: str | None = None,
        local_fallback_dir: Path | None = None,
    ) -> None:
        self.endpoint_url = endpoint_url or settings.GARAGE_S3_ENDPOINT_URL
        self.region_name = region_name or settings.GARAGE_S3_REGION
        self.access_key_id = access_key_id or settings.GARAGE_S3_ACCESS_KEY_ID
        raw_secret = (
            secret_access_key
            or (
                settings.GARAGE_S3_SECRET_ACCESS_KEY.get_secret_value()
                if settings.GARAGE_S3_SECRET_ACCESS_KEY
                else None
            )
            or (
                settings.MINIO_ROOT_PASSWORD.get_secret_value()
                if settings.MINIO_ROOT_PASSWORD
                else None
            )
        )
        self.secret_access_key = raw_secret
        self.bucket_name = bucket_name or settings.GARAGE_S3_BUCKET
        self.local_fallback_dir = local_fallback_dir or (BASE_DIR / "storage" / "football-s3")
        self.local_fallback_dir.mkdir(parents=True, exist_ok=True)

    def _build_s3_client(self) -> Any:
        addressing_style = "path" if settings.GARAGE_S3_FORCE_PATH_STYLE else "auto"
        return boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            region_name=self.region_name,
            aws_access_key_id=self.access_key_id or "garage-dev-key",
            aws_secret_access_key=self.secret_access_key or "garage-dev-secret",
            config=BotoConfig(
                signature_version="s3v4",
                s3={"addressing_style": addressing_style},
                connect_timeout=2,
                read_timeout=5,
                retries={"max_attempts": 1},
            ),
        )

    @staticmethod
    def compute_sha256(payload: bytes) -> str:
        return hashlib.sha256(payload).hexdigest()

    def put_object_bytes(
        self,
        object_key: str,
        payload: bytes,
        content_type: str = "application/octet-stream",
        prefer_local: bool = False,
    ) -> tuple[str, str]:
        """
        Store `payload` under `object_key` in Garage S3 (or local fallback) and return
        `(storage_uri, sha256_hex)`.
        """
        sha256_hex = self.compute_sha256(payload)
        normalized_key = object_key.lstrip("/")

        if not prefer_local and self.access_key_id and self.secret_access_key:
            try:
                client = self._build_s3_client()
                client.put_object(
                    Bucket=self.bucket_name,
                    Key=normalized_key,
                    Body=payload,
                    ContentType=content_type,
                    Metadata={"sha256": sha256_hex},
                )
                return f"s3://{self.bucket_name}/{normalized_key}", sha256_hex
            except (BotoCoreError, ClientError, OSError) as exc:
                logger.warning(
                    "Garage S3 endpoint unreachable (%s), using local structured storage fallback.",
                    exc,
                )

        target_path = self.local_fallback_dir / self.bucket_name / normalized_key
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(payload)
        return f"s3://{self.bucket_name}/{normalized_key}", sha256_hex

    def generate_signed_url(
        self,
        object_key: str,
        expires_in_seconds: int | None = None,
    ) -> str:
        """Generate a short-lived signed URL for authorized access to evidence files."""
        cfg = load_football_config()
        ttl = expires_in_seconds or cfg.session.presigned_url_ttl_seconds
        normalized_key = object_key.lstrip("/")
        expires_at = int(time.time()) + ttl
        signing_secret = settings.SECRET_KEY.get_secret_value().encode("utf-8")
        message = f"{self.bucket_name}:{normalized_key}:{expires_at}".encode()
        signature = hmac.new(signing_secret, message, hashlib.sha256).hexdigest()
        base = self.endpoint_url.rstrip("/")
        return (
            f"{base}/{self.bucket_name}/{normalized_key}"
            f"?X-SkillMatch-Expires={expires_at}&X-SkillMatch-Signature={signature}"
        )


garage_s3_storage = GarageS3StorageService()
