"""HU-39 session completion, presence PINs and no-show reports.

Revision ID: d49e1f5a8b72
Revises: c3bea441869b
Create Date: 2026-11-18 23:27:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d49e1f5a8b72"
down_revision: str | Sequence[str] | None = "c3bea441869b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Expand exchange_sessions status constraint to include COMPLETED
    op.drop_constraint("ck_exchange_sessions_status", "exchange_sessions", type_="check")
    op.create_check_constraint(
        "ck_exchange_sessions_status",
        "exchange_sessions",
        "status IN ('PENDING', 'ACCEPTED', 'REJECTED', 'CANCELLED', 'COMPLETED')",
    )

    # 2. Add actual_minutes, completed_at, completion_version to exchange_sessions
    op.add_column("exchange_sessions", sa.Column("actual_minutes", sa.SmallInteger(), nullable=True))
    op.create_check_constraint(
        "ck_exchange_sessions_actual_minutes",
        "exchange_sessions",
        "actual_minutes IS NULL OR (actual_minutes >= 1 AND actual_minutes <= 60)",
    )
    op.add_column("exchange_sessions", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "exchange_sessions",
        sa.Column("completion_version", sa.Integer(), nullable=False, server_default="1"),
    )

    # 3. Create session_confirmations
    op.create_table(
        "session_confirmations",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "session_id",
            sa.UUID(),
            sa.ForeignKey("exchange_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("actual_minutes", sa.SmallInteger(), nullable=False),
        sa.Column("topics", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("modality", sa.String(length=20), nullable=False),
        sa.Column(
            "confirmed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("request_key", sa.UUID(), nullable=False),
        sa.CheckConstraint("actual_minutes >= 1 AND actual_minutes <= 60", name="ck_session_confirmations_minutes"),
        sa.CheckConstraint("modality IN ('VIRTUAL', 'PRESENCIAL')", name="ck_session_confirmations_modality"),
        sa.UniqueConstraint("session_id", "user_id", name="uq_session_confirmations_session_user"),
        sa.UniqueConstraint("request_key", name="uq_session_confirmations_request_key"),
    )
    op.create_index(
        "ix_session_confirmations_session_user",
        "session_confirmations",
        ["session_id", "user_id"],
    )

    # 4. Create session_presence_pins
    op.create_table(
        "session_presence_pins",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "session_id",
            sa.UUID(),
            sa.ForeignKey("exchange_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("pin_hash", sa.String(length=255), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint("attempt_count >= 0 AND attempt_count <= 5", name="ck_session_presence_pins_attempts"),
        sa.UniqueConstraint("session_id", "user_id", name="uq_session_presence_pins_session_user"),
    )
    op.create_index(
        "ix_session_presence_pins_lookup",
        "session_presence_pins",
        ["session_id", "user_id"],
    )

    # 5. Create session_no_show_reports
    op.create_table(
        "session_no_show_reports",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "session_id",
            sa.UUID(),
            sa.ForeignKey("exchange_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "reported_by_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "absent_user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING_REPUTATION"),
        sa.Column(
            "reported_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("request_key", sa.UUID(), nullable=False),
        sa.CheckConstraint("reported_by_id <> absent_user_id", name="ck_session_no_show_distinct_users"),
        sa.CheckConstraint("length(btrim(reason)) BETWEEN 10 AND 500", name="ck_session_no_show_reason"),
        sa.CheckConstraint(
            "status IN ('PENDING_REPUTATION', 'PROCESSED', 'DISMISSED')",
            name="ck_session_no_show_status",
        ),
        sa.UniqueConstraint("session_id", "absent_user_id", name="uq_session_no_show_session_absent"),
        sa.UniqueConstraint("request_key", name="uq_session_no_show_request_key"),
    )
    op.create_index("ix_session_no_show_session", "session_no_show_reports", ["session_id"])

    # 6. Update session_audit_events type constraint
    op.drop_constraint("ck_session_audit_events_type", "session_audit_events", type_="check")
    op.create_check_constraint(
        "ck_session_audit_events_type",
        "session_audit_events",
        "event_type IN ('CREATED', 'ACCEPTED', 'REJECTED', 'RESCHEDULED', 'CANCELLED', "
        "'QUOTA_RESERVED', 'QUOTA_RELEASED', 'QUOTA_RESTORED', 'BOOKING_BLOCKED', "
        "'CONFIRMATION_RECORDED', 'COMPLETED', 'NO_SHOW_REPORTED')",
    )

    # 7. Update notifications type constraint
    op.drop_constraint("ck_notifications_type", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notifications_type",
        "notifications",
        "type IN ('MATCH_RECEIVED', 'MATCH_CONFIRMED', 'SESSION_PROPOSED', "
        "'SESSION_ACCEPTED', 'SESSION_REJECTED', 'SESSION_RESCHEDULED', "
        "'SESSION_CANCELLED', 'SESSION_REMINDER', 'SESSION_CONFIRMATION_RECORDED', "
        "'SESSION_COMPLETED', 'SESSION_NO_SHOW_REPORTED', 'POINTS_RECEIVED', 'OTHER')",
    )


def downgrade() -> None:
    # 7. Revert notifications type constraint
    op.drop_constraint("ck_notifications_type", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notifications_type",
        "notifications",
        "type IN ('MATCH_RECEIVED', 'MATCH_CONFIRMED', 'SESSION_PROPOSED', "
        "'SESSION_ACCEPTED', 'SESSION_REJECTED', 'SESSION_RESCHEDULED', "
        "'SESSION_CANCELLED', 'SESSION_REMINDER', 'POINTS_RECEIVED', 'OTHER')",
    )

    # 6. Revert session_audit_events type constraint
    op.drop_constraint("ck_session_audit_events_type", "session_audit_events", type_="check")
    op.create_check_constraint(
        "ck_session_audit_events_type",
        "session_audit_events",
        "event_type IN ('CREATED', 'ACCEPTED', 'REJECTED', 'RESCHEDULED', 'CANCELLED', "
        "'QUOTA_RESERVED', 'QUOTA_RELEASED', 'QUOTA_RESTORED', 'BOOKING_BLOCKED')",
    )

    # 5. Drop session_no_show_reports
    op.drop_index("ix_session_no_show_session", table_name="session_no_show_reports")
    op.drop_table("session_no_show_reports")

    # 4. Drop session_presence_pins
    op.drop_index("ix_session_presence_pins_lookup", table_name="session_presence_pins")
    op.drop_table("session_presence_pins")

    # 3. Drop session_confirmations
    op.drop_index("ix_session_confirmations_session_user", table_name="session_confirmations")
    op.drop_table("session_confirmations")

    # 2. Drop columns from exchange_sessions
    op.drop_column("exchange_sessions", "completion_version")
    op.drop_column("exchange_sessions", "completed_at")
    op.drop_constraint("ck_exchange_sessions_actual_minutes", "exchange_sessions", type_="check")
    op.drop_column("exchange_sessions", "actual_minutes")

    # 1. Revert exchange_sessions status constraint
    op.drop_constraint("ck_exchange_sessions_status", "exchange_sessions", type_="check")
    op.create_check_constraint(
        "ck_exchange_sessions_status",
        "exchange_sessions",
        "status IN ('PENDING', 'ACCEPTED', 'REJECTED', 'CANCELLED')",
    )
