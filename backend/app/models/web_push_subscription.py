"""Private browser/PWA Web Push subscriptions owned by one member."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class WebPushSubscription(Base, TimestampMixin):
    __tablename__ = "web_push_subscriptions"
    __table_args__ = (
        UniqueConstraint("endpoint_hash", name="uq_web_push_subscriptions_endpoint_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE", name="fk_web_push_subscriptions_user_id"),
        nullable=False,
    )
    endpoint: Mapped[str] = mapped_column(String(2048), nullable=False)
    endpoint_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    p256dh: Mapped[str] = mapped_column(String(4096), nullable=False)
    auth: Mapped[str] = mapped_column(String(1024), nullable=False)
    device_label: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


Index(
    "ix_web_push_subscriptions_user_active",
    WebPushSubscription.user_id,
    WebPushSubscription.is_active,
)
Index(
    "ix_web_push_subscriptions_active_updated",
    WebPushSubscription.updated_at,
    postgresql_where=WebPushSubscription.is_active.is_(True),
)
