"""Strict private contracts for Web Push device subscriptions."""

from datetime import datetime
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class WebPushSubscriptionKeys(BaseModel):
    model_config = ConfigDict(extra="forbid")

    p256dh: str = Field(strict=True, min_length=1, max_length=4096)
    auth: str = Field(strict=True, min_length=1, max_length=1024)

    @field_validator("p256dh", "auth")
    @classmethod
    def strip_key(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("La clave de suscripción es obligatoria")
        return stripped


class WebPushSubscriptionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endpoint: str = Field(strict=True, min_length=1, max_length=2048)
    keys: WebPushSubscriptionKeys
    device_label: str = Field(strict=True, min_length=1, max_length=100)

    @field_validator("endpoint")
    @classmethod
    def require_https_capability_url(cls, value: str) -> str:
        stripped = value.strip()
        parsed = urlsplit(stripped)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("El endpoint Web Push debe usar HTTPS")
        if parsed.username or parsed.password or parsed.fragment:
            raise ValueError("El endpoint Web Push contiene componentes no permitidos")
        return stripped

    @field_validator("device_label")
    @classmethod
    def strip_device_label(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("La etiqueta del dispositivo es obligatoria")
        return stripped


class WebPushPublicKeyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    public_key: str = Field(min_length=1)


class WebPushSubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    endpoint: str
    device_label: str
    is_active: bool
    created_at: datetime
