import uuid
from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NotificationType(str, Enum):
    MATCH_RECEIVED = "MATCH_RECEIVED"
    MATCH_CONFIRMED = "MATCH_CONFIRMED"
    SESSION_PROPOSED = "SESSION_PROPOSED"
    SESSION_ACCEPTED = "SESSION_ACCEPTED"
    SESSION_REJECTED = "SESSION_REJECTED"
    SESSION_RESCHEDULED = "SESSION_RESCHEDULED"
    SESSION_CANCELLED = "SESSION_CANCELLED"
    SESSION_REMINDER = "SESSION_REMINDER"
    POINTS_RECEIVED = "POINTS_RECEIVED"
    OTHER = "OTHER"


class NotificationCategory(str, Enum):
    INTERCHANGES = "INTERCHANGES"
    POINTS = "POINTS"
    GENERAL = "GENERAL"


NOTIFICATION_CATEGORIES = {
    NotificationType.MATCH_RECEIVED: NotificationCategory.INTERCHANGES,
    NotificationType.MATCH_CONFIRMED: NotificationCategory.INTERCHANGES,
    NotificationType.SESSION_PROPOSED: NotificationCategory.INTERCHANGES,
    NotificationType.SESSION_ACCEPTED: NotificationCategory.INTERCHANGES,
    NotificationType.SESSION_REJECTED: NotificationCategory.INTERCHANGES,
    NotificationType.SESSION_RESCHEDULED: NotificationCategory.INTERCHANGES,
    NotificationType.SESSION_CANCELLED: NotificationCategory.INTERCHANGES,
    NotificationType.SESSION_REMINDER: NotificationCategory.INTERCHANGES,
    NotificationType.POINTS_RECEIVED: NotificationCategory.POINTS,
    NotificationType.OTHER: NotificationCategory.GENERAL,
}


class Notification(Base):
    """Personal inbox record; deletion never deletes its domain event/audit."""

    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("user_id", "event_id", name="uq_notifications_user_event"),
        CheckConstraint(
            "type IN ('MATCH_RECEIVED', 'MATCH_CONFIRMED', 'SESSION_PROPOSED', "
            "'SESSION_ACCEPTED', 'SESSION_REJECTED', 'SESSION_RESCHEDULED', "
            "'SESSION_CANCELLED', 'SESSION_REMINDER', 'POINTS_RECEIVED', 'OTHER')",
            name="ck_notifications_type",
        ),
        CheckConstraint("length(btrim(title)) > 0", name="ck_notifications_title"),
        CheckConstraint("length(btrim(message)) > 0", name="ck_notifications_message"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE", name="fk_notifications_user_id"),
        nullable=False,
    )
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    message: Mapped[str] = mapped_column(String(2000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def category(self) -> NotificationCategory:
        return NOTIFICATION_CATEGORIES[NotificationType(self.type)]


Index(
    "ix_notifications_user_visible_order",
    Notification.user_id,
    Notification.created_at.desc(),
    Notification.id,
    postgresql_where=Notification.deleted_at.is_(None),
)
Index(
    "ix_notifications_user_unread",
    Notification.user_id,
    postgresql_where=Notification.read_at.is_(None) & Notification.deleted_at.is_(None),
)
