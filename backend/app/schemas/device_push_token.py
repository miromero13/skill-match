"""Contracts for mobile device push tokens (FCM)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DevicePushTokenRegister(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fcm_token: str = Field(strict=True, min_length=10, max_length=512)
    platform: str = Field(default="android", min_length=2, max_length=20)
    device_label: str | None = Field(default=None, max_length=100)

    @field_validator("fcm_token")
    @classmethod
    def strip_token(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("El token FCM es obligatorio")
        return stripped


class DevicePushTokenResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    platform: str
    device_label: str | None
    is_active: bool
    created_at: datetime
