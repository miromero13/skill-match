import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, false, true
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class NotificationPreference(Base, TimestampMixin):
    """Persisted preferences start at revision 1; implicit defaults use revision 0."""

    __tablename__ = "notification_preferences"
    __table_args__ = (
        CheckConstraint("revision >= 1", name="ck_notification_preferences_revision"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE", name="fk_notification_preferences_user_id"),
        primary_key=True,
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    in_app: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
    push: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    email: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    interchanges: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
    points: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
    general: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
