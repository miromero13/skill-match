"""Add idempotent HU-38 session reminder dispatches.

Revision ID: f38d5b7c8e93
Revises: e38c4a6b7d82
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f38d5b7c8e93"
down_revision: str | None = "e38c4a6b7d82"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "session_reminder_dispatches",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("threshold", sa.String(length=3), nullable=False),
        sa.Column("session_starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_id", sa.UUID(), nullable=False),
        sa.Column("notification_id", sa.UUID(), nullable=True),
        sa.Column(
            "dispatched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "threshold IN ('24H', '1H')", name="ck_session_reminder_threshold",
        ),
        sa.ForeignKeyConstraint(
            ["notification_id"], ["notifications.id"], ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["exchange_sessions.id"], ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", name="uq_session_reminder_dispatch_event"),
        sa.UniqueConstraint(
            "session_id",
            "user_id",
            "threshold",
            "session_starts_at",
            name="uq_session_reminder_dispatch_identity",
        ),
    )
    op.create_index(
        "ix_session_reminder_dispatch_due",
        "session_reminder_dispatches",
        ["session_id", "session_starts_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_session_reminder_dispatch_due", table_name="session_reminder_dispatches",
    )
    op.drop_table("session_reminder_dispatches")
