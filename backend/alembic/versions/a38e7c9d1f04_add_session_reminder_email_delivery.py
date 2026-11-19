"""Add auditable SMTP delivery for HU-38 session reminders.

Revision ID: a38e7c9d1f04
Revises: f38d5b7c8e93
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a38e7c9d1f04"
down_revision: str | None = "f38d5b7c8e93"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "session_reminder_email_deliveries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("dispatch_id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("event_id", sa.UUID(), nullable=False),
        sa.Column("message_id", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_error_kind", sa.String(length=32), nullable=True),
        sa.Column("skipped_reason", sa.String(length=64), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "attempt_count BETWEEN 0 AND 3",
            name="ck_session_reminder_email_attempts",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'SENT', 'FAILED', 'SKIPPED')",
            name="ck_session_reminder_email_status",
        ),
        sa.ForeignKeyConstraint(
            ["dispatch_id"], ["session_reminder_dispatches.id"], ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["exchange_sessions.id"], ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dispatch_id", name="uq_session_reminder_email_dispatch"),
        sa.UniqueConstraint("event_id", name="uq_session_reminder_email_event"),
        sa.UniqueConstraint("message_id", name="uq_session_reminder_email_message_id"),
    )
    op.create_index(
        "ix_session_reminder_email_pending",
        "session_reminder_email_deliveries",
        ["status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_session_reminder_email_pending",
        table_name="session_reminder_email_deliveries",
    )
    op.drop_table("session_reminder_email_deliveries")
