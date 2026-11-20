"""FCM device push tokens for native mobile push notifications."""

import uuid

from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class DevicePushToken(Base, TimestampMixin):
    __tablename__ = "device_push_tokens"
    __table_args__ = (
        UniqueConstraint("fcm_token", name="uq_device_push_tokens_fcm_token"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE", name="fk_device_push_tokens_user_id"),
        nullable=False,
    )
    fcm_token: Mapped[str] = mapped_column(String(512), nullable=False)
    platform: Mapped[str] = mapped_column(String(20), nullable=False, default="android")
    device_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


Index(
    "ix_device_push_tokens_user_active",
    DevicePushToken.user_id,
    DevicePushToken.is_active,
)
