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

    def get_object_bytes(
        self,
        object_key: str,
        prefer_local: bool = False,
    ) -> bytes:
        """Read `object_key` bytes from Garage S3 (or local fallback)."""
        normalized_key = object_key.lstrip("/")
        local_path = self.local_fallback_dir / self.bucket_name / normalized_key
        if prefer_local and local_path.exists():
            return local_path.read_bytes()

        if not prefer_local and self.access_key_id and self.secret_access_key:
            try:
                client = self._build_s3_client()
                response = client.get_object(Bucket=self.bucket_name, Key=normalized_key)
                return bytes(response["Body"].read())
            except (BotoCoreError, ClientError, OSError) as exc:
                logger.warning(
                    "Falling back to local storage for get_object(%s): %s",
                    normalized_key,
                    exc,
                )

        if local_path.exists():
            return local_path.read_bytes()
        raise FileNotFoundError(f"Object not found in storage: {normalized_key}")

    def list_chunk_indices(
        self,
        session_id: str,
        prefer_local: bool = False,
    ) -> list[tuple[int, str]]:
        """
        Return sorted list of `(chunk_index, object_key)` uploaded for `session_id`.
        """
        prefix = f"sessions/{session_id}/chunks/"
        found: dict[int, str] = {}

        if not prefer_local and self.access_key_id and self.secret_access_key:
            try:
                client = self._build_s3_client()
                paginator = client.get_paginator("list_objects_v2")
                for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                    for item in page.get("Contents", []):
                        key = str(item["Key"])
                        filename = key.rsplit("/", 1)[-1]
                        idx_str = filename.split(".", 1)[0]
                        if idx_str.isdigit():
                            found[int(idx_str)] = key
                if found:
                    return sorted(found.items(), key=lambda pair: pair[0])
            except (BotoCoreError, ClientError, OSError) as exc:
                logger.warning("Falling back to local storage for list_chunk_indices: %s", exc)

        local_dir = self.local_fallback_dir / self.bucket_name / "sessions" / session_id / "chunks"
        if local_dir.exists():
            for child in local_dir.iterdir():
                if child.is_file():
                    idx_str = child.name.split(".", 1)[0]
                    if idx_str.isdigit():
                        found[int(idx_str)] = f"{prefix}{child.name}"

        return sorted(found.items(), key=lambda pair: pair[0])

    def assemble_session_chunks(
        self,
        session_id: str,
        extension: str = "mp4",
        content_type: str = "video/mp4",
        prefer_local: bool = False,
    ) -> tuple[str, str, int, list[int]]:
        """
        Verify contiguous chunks `0..N-1` for `session_id`, concatenate them into
        `sessions/{session_id}/assembled/recording.{extension}`, upload to Garage S3,
        and return `(storage_uri, sha256_hex, total_bytes, chunk_indices)`.
        """
        chunk_entries = self.list_chunk_indices(session_id=session_id, prefer_local=prefer_local)
        if not chunk_entries:
            raise ValueError("No se encontraron fragmentos subidos para esta sesión.")

        indices = [idx for idx, _ in chunk_entries]
        expected_indices = list(range(len(indices)))
        if indices != expected_indices:
            missing = sorted(set(range(max(indices) + 1)) - set(indices))
            raise ValueError(
                f"Faltan fragmentos por subir antes de finalizar la sesión: {missing}"
            )

        assembled_parts: list[bytes] = []
        for _, key in chunk_entries:
            assembled_parts.append(self.get_object_bytes(key, prefer_local=prefer_local))

        assembled_bytes = b"".join(assembled_parts)
        assembled_key = f"sessions/{session_id}/assembled/recording.{extension.lstrip('.')}"
        storage_uri, sha256_hex = self.put_object_bytes(
            object_key=assembled_key,
            payload=assembled_bytes,
            content_type=content_type,
            prefer_local=prefer_local,
        )
        return storage_uri, sha256_hex, len(assembled_bytes), indices

    def generate_signed_url(
        self,
        object_key: str,
        expires_in_seconds: int | None = None,
    ) -> str:
        """Generate a short-lived S3v4 presigned URL (with HMAC fallback) for authorized access."""
        cfg = load_football_config()
        ttl = expires_in_seconds or cfg.session.presigned_url_ttl_seconds
        normalized_key = object_key.lstrip("/")
        if self.access_key_id and self.secret_access_key:
            try:
                client = self._build_s3_client()
                return str(
                    client.generate_presigned_url(
                        "get_object",
                        Params={"Bucket": self.bucket_name, "Key": normalized_key},
                        ExpiresIn=ttl,
                    )
                )
            except (BotoCoreError, ClientError):
                pass
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
