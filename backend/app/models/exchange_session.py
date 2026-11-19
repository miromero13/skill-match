from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class ExchangeSession(Base, TimestampMixin):
    __tablename__ = "exchange_sessions"
    __table_args__ = (
        CheckConstraint(
            "instructor_id <> learner_id", name="ck_exchange_sessions_distinct_members"
        ),
        CheckConstraint(
            "ends_at > starts_at AND ends_at <= starts_at + interval '60 minutes'",
            name="ck_exchange_sessions_duration",
        ),
        CheckConstraint(
            "modality IN ('VIRTUAL', 'PRESENCIAL')",
            name="ck_exchange_sessions_modality",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'ACCEPTED', 'REJECTED', 'CANCELLED')",
            name="ck_exchange_sessions_status",
        ),
        CheckConstraint(
            "points_required IS NULL OR points_required >= 0",
            name="ck_exchange_sessions_points_required",
        ),
        CheckConstraint(
            "payment_state IS NULL OR payment_state IN "
            "('PENDING', 'RESERVED', 'REFUNDED', 'RELEASED')",
            name="ck_exchange_sessions_payment_state",
        ),
        CheckConstraint(
            "cancellation_reason IS NULL OR length(btrim(cancellation_reason)) BETWEEN 10 AND 500",
            name="ck_exchange_sessions_cancellation_reason",
        ),
        Index("ix_exchange_sessions_learner_starts", "learner_id", "starts_at"),
        Index("ix_exchange_sessions_instructor_starts", "instructor_id", "starts_at"),
        Index("ix_exchange_sessions_match_status", "match_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    match_id: Mapped[UUID] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"),
        nullable=False,
    )
    teaching_skill_id: Mapped[UUID] = mapped_column(
        ForeignKey("user_teaching_skills.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_by_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    instructor_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    learner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timezone: Mapped[str] = mapped_column(String(100), nullable=False)
    modality: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    is_free: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    points_required: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payment_state: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cancelled_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    quota_restored: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class WeeklySessionQuota(Base, TimestampMixin):
    __tablename__ = "weekly_session_quotas"
    __table_args__ = (
        UniqueConstraint("user_id", "week_start", name="uq_weekly_session_quota_user_week"),
        CheckConstraint("used >= 0 AND used <= 2", name="ck_weekly_session_quotas_used"),
        CheckConstraint("version >= 1", name="ck_weekly_session_quotas_version"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class SessionQuotaMovement(Base):
    __tablename__ = "session_quota_movements"
    __table_args__ = (
        CheckConstraint("delta IN (-1, 1)", name="ck_session_quota_movements_delta"),
        CheckConstraint(
            "kind IN ('RESERVED', 'RELEASED', 'RESTORED')",
            name="ck_session_quota_movements_kind",
        ),
        Index("ix_session_quota_movements_session", "session_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    quota_id: Mapped[UUID] = mapped_column(
        ForeignKey("weekly_session_quotas.id", ondelete="CASCADE"),
        nullable=False,
    )
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("exchange_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )


class SessionCancellation(Base):
    __tablename__ = "session_cancellations"
    __table_args__ = (
        UniqueConstraint("session_id", name="uq_session_cancellations_session"),
        CheckConstraint(
            "length(btrim(reason)) BETWEEN 10 AND 500",
            name="ck_session_cancellations_reason",
        ),
        Index("ix_session_cancellations_actor_time", "cancelled_by_id", "cancelled_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("exchange_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    cancelled_by_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    cancelled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_timely: Mapped[bool] = mapped_column(Boolean, nullable=False)
    quota_restored: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    triggers_booking_block: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class BookingRestriction(Base, TimestampMixin):
    __tablename__ = "booking_restrictions"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ck_booking_restrictions_period"),
        CheckConstraint(
            "reason IN ('LATE_CANCELLATION', 'MONTHLY_CANCELLATIONS')",
            name="ck_booking_restrictions_reason",
        ),
        UniqueConstraint(
            "user_id",
            "source_session_id",
            "reason",
            name="uq_booking_restriction_source",
        ),
        Index("ix_booking_restrictions_user_period", "user_id", "starts_at", "ends_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("exchange_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(String(32), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SessionAuditEvent(Base):
    __tablename__ = "session_audit_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN "
            "('CREATED', 'ACCEPTED', 'REJECTED', 'RESCHEDULED', 'CANCELLED', "
            "'QUOTA_RESERVED', 'QUOTA_RELEASED', 'QUOTA_RESTORED', 'BOOKING_BLOCKED')",
            name="ck_session_audit_events_type",
        ),
        Index("ix_session_audit_events_session_time", "session_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("exchange_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    actor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )


class SessionReminderDispatch(Base):
    __tablename__ = "session_reminder_dispatches"
    __table_args__ = (
        CheckConstraint("threshold IN ('24H', '1H')", name="ck_session_reminder_threshold"),
        UniqueConstraint(
            "session_id",
            "user_id",
            "threshold",
            "session_starts_at",
            name="uq_session_reminder_dispatch_identity",
        ),
        UniqueConstraint("event_id", name="uq_session_reminder_dispatch_event"),
        Index("ix_session_reminder_dispatch_due", "session_id", "session_starts_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("exchange_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    threshold: Mapped[str] = mapped_column(String(3), nullable=False)
    session_starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    event_id: Mapped[UUID] = mapped_column(nullable=False)
    notification_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("notifications.id", ondelete="SET NULL"),
        nullable=True,
    )
    dispatched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )


class SessionReminderEmailDelivery(Base, TimestampMixin):
    __tablename__ = "session_reminder_email_deliveries"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'SENT', 'FAILED', 'SKIPPED')",
            name="ck_session_reminder_email_status",
        ),
        CheckConstraint(
            "attempt_count BETWEEN 0 AND 3",
            name="ck_session_reminder_email_attempts",
        ),
        UniqueConstraint("dispatch_id", name="uq_session_reminder_email_dispatch"),
        UniqueConstraint("event_id", name="uq_session_reminder_email_event"),
        UniqueConstraint("message_id", name="uq_session_reminder_email_message_id"),
        Index("ix_session_reminder_email_pending", "status", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    dispatch_id: Mapped[UUID] = mapped_column(
        ForeignKey("session_reminder_dispatches.id", ondelete="CASCADE"),
        nullable=False,
    )
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("exchange_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_id: Mapped[UUID] = mapped_column(nullable=False)
    message_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    skipped_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SessionReminderWebPushDelivery(Base, TimestampMixin):
    __tablename__ = "session_reminder_web_push_deliveries"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'SENT', 'FAILED', 'SKIPPED')",
            name="ck_session_reminder_web_push_status",
        ),
        CheckConstraint(
            "attempt_count BETWEEN 0 AND 3",
            name="ck_session_reminder_web_push_attempts",
        ),
        UniqueConstraint(
            "event_id",
            "subscription_id",
            name="uq_session_reminder_web_push_event_subscription",
        ),
        UniqueConstraint("delivery_id", name="uq_session_reminder_web_push_delivery_id"),
        Index("ix_session_reminder_web_push_pending", "status", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    dispatch_id: Mapped[UUID] = mapped_column(
        ForeignKey("session_reminder_dispatches.id", ondelete="CASCADE"),
        nullable=False,
    )
    subscription_id: Mapped[UUID] = mapped_column(
        ForeignKey("web_push_subscriptions.id", ondelete="CASCADE"),
        nullable=False,
    )
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("exchange_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_id: Mapped[UUID] = mapped_column(nullable=False)
    delivery_id: Mapped[UUID] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_error_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    skipped_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
