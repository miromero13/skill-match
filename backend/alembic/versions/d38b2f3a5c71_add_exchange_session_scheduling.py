"""Add HU-38 exchange session scheduling persistence.

Revision ID: d38b2f3a5c71
Revises: c38a1e2f4b60
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d38b2f3a5c71"
down_revision: str | Sequence[str] | None = "c38a1e2f4b60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "exchange_sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("match_id", sa.UUID(), nullable=False),
        sa.Column("teaching_skill_id", sa.UUID(), nullable=False),
        sa.Column("created_by_id", sa.UUID(), nullable=False),
        sa.Column("instructor_id", sa.UUID(), nullable=False),
        sa.Column("learner_id", sa.UUID(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone", sa.String(length=100), nullable=False),
        sa.Column("modality", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("is_free", sa.Boolean(), nullable=False),
        sa.Column("points_required", sa.Integer(), nullable=True),
        sa.Column("payment_state", sa.String(length=20), nullable=True),
        sa.Column("cancellation_reason", sa.String(length=500), nullable=True),
        sa.Column("cancelled_by_id", sa.UUID(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("quota_restored", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "cancellation_reason IS NULL OR length(btrim(cancellation_reason)) BETWEEN 10 AND 500",
            name="ck_exchange_sessions_cancellation_reason",
        ),
        sa.CheckConstraint(
            "ends_at > starts_at AND ends_at <= starts_at + interval '60 minutes'",
            name="ck_exchange_sessions_duration",
        ),
        sa.CheckConstraint(
            "instructor_id <> learner_id", name="ck_exchange_sessions_distinct_members",
        ),
        sa.CheckConstraint(
            "modality IN ('VIRTUAL', 'PRESENCIAL')", name="ck_exchange_sessions_modality",
        ),
        sa.CheckConstraint(
            "payment_state IS NULL OR payment_state IN "
            "('PENDING', 'RESERVED', 'REFUNDED', 'RELEASED')",
            name="ck_exchange_sessions_payment_state",
        ),
        sa.CheckConstraint(
            "points_required IS NULL OR points_required >= 0",
            name="ck_exchange_sessions_points_required",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'ACCEPTED', 'REJECTED', 'CANCELLED')",
            name="ck_exchange_sessions_status",
        ),
        sa.ForeignKeyConstraint(["cancelled_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["instructor_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["learner_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["match_id"], ["matches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["teaching_skill_id"], ["user_teaching_skills.id"], ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_exchange_sessions_instructor_starts",
        "exchange_sessions", ["instructor_id", "starts_at"], unique=False,
    )
    op.create_index(
        "ix_exchange_sessions_learner_starts",
        "exchange_sessions", ["learner_id", "starts_at"], unique=False,
    )
    op.create_index(
        "ix_exchange_sessions_match_status",
        "exchange_sessions", ["match_id", "status"], unique=False,
    )

    op.create_table(
        "weekly_session_quotas",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("used", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("used >= 0 AND used <= 2", name="ck_weekly_session_quotas_used"),
        sa.CheckConstraint("version >= 1", name="ck_weekly_session_quotas_version"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "week_start", name="uq_weekly_session_quota_user_week"),
    )
    op.create_index(
        op.f("ix_weekly_session_quotas_user_id"),
        "weekly_session_quotas", ["user_id"], unique=False,
    )

    op.create_table(
        "session_quota_movements",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("quota_id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False,
        ),
        sa.CheckConstraint("delta IN (-1, 1)", name="ck_session_quota_movements_delta"),
        sa.CheckConstraint(
            "kind IN ('RESERVED', 'RELEASED', 'RESTORED')",
            name="ck_session_quota_movements_kind",
        ),
        sa.ForeignKeyConstraint(
            ["quota_id"], ["weekly_session_quotas.id"], ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["exchange_sessions.id"], ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_session_quota_movements_session",
        "session_quota_movements", ["session_id", "created_at"], unique=False,
    )

    op.create_table(
        "session_cancellations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("cancelled_by_id", sa.UUID(), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_timely", sa.Boolean(), nullable=False),
        sa.Column("quota_restored", sa.Boolean(), nullable=False),
        sa.Column("triggers_booking_block", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "length(btrim(reason)) BETWEEN 10 AND 500",
            name="ck_session_cancellations_reason",
        ),
        sa.ForeignKeyConstraint(["cancelled_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["session_id"], ["exchange_sessions.id"], ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", name="uq_session_cancellations_session"),
    )
    op.create_index(
        "ix_session_cancellations_actor_time",
        "session_cancellations", ["cancelled_by_id", "cancelled_at"], unique=False,
    )

    op.create_table(
        "booking_restrictions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("source_session_id", sa.UUID(), nullable=False),
        sa.Column("reason", sa.String(length=32), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("ends_at > starts_at", name="ck_booking_restrictions_period"),
        sa.CheckConstraint(
            "reason IN ('LATE_CANCELLATION', 'MONTHLY_CANCELLATIONS')",
            name="ck_booking_restrictions_reason",
        ),
        sa.ForeignKeyConstraint(
            ["source_session_id"], ["exchange_sessions.id"], ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "source_session_id", "reason", name="uq_booking_restriction_source",
        ),
    )
    op.create_index(
        "ix_booking_restrictions_user_period",
        "booking_restrictions", ["user_id", "starts_at", "ends_at"], unique=False,
    )

    op.create_table(
        "session_audit_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("actor_id", sa.UUID(), nullable=True),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("from_status", sa.String(length=20), nullable=True),
        sa.Column("to_status", sa.String(length=20), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False,
        ),
        sa.CheckConstraint(
            "event_type IN "
            "('CREATED', 'ACCEPTED', 'REJECTED', 'RESCHEDULED', 'CANCELLED', "
            "'QUOTA_RESERVED', 'QUOTA_RELEASED', 'QUOTA_RESTORED', 'BOOKING_BLOCKED')",
            name="ck_session_audit_events_type",
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["session_id"], ["exchange_sessions.id"], ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_session_audit_events_session_time",
        "session_audit_events", ["session_id", "created_at"], unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_session_audit_events_session_time", table_name="session_audit_events")
    op.drop_table("session_audit_events")
    op.drop_index("ix_booking_restrictions_user_period", table_name="booking_restrictions")
    op.drop_table("booking_restrictions")
    op.drop_index("ix_session_cancellations_actor_time", table_name="session_cancellations")
    op.drop_table("session_cancellations")
    op.drop_index("ix_session_quota_movements_session", table_name="session_quota_movements")
    op.drop_table("session_quota_movements")
    op.drop_index(op.f("ix_weekly_session_quotas_user_id"), table_name="weekly_session_quotas")
    op.drop_table("weekly_session_quotas")
    op.drop_index("ix_exchange_sessions_match_status", table_name="exchange_sessions")
    op.drop_index("ix_exchange_sessions_learner_starts", table_name="exchange_sessions")
    op.drop_index("ix_exchange_sessions_instructor_starts", table_name="exchange_sessions")
    op.drop_table("exchange_sessions")
