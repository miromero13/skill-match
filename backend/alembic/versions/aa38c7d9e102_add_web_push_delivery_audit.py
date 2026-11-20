"""Add auditable Web Push reminder deliveries for HU-38."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "aa38c7d9e102"
down_revision: str | None = "b38f6d7e8a90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "session_reminder_web_push_deliveries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("dispatch_id", sa.UUID(), nullable=False),
        sa.Column("subscription_id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("event_id", sa.UUID(), nullable=False),
        sa.Column("delivery_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_status_code", sa.Integer(), nullable=True),
        sa.Column("last_error_kind", sa.String(32), nullable=True),
        sa.Column("skipped_reason", sa.String(64), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("attempt_count BETWEEN 0 AND 3", name="ck_session_reminder_web_push_attempts"),
        sa.CheckConstraint("status IN ('PENDING', 'SENT', 'FAILED', 'SKIPPED')", name="ck_session_reminder_web_push_status"),
        sa.ForeignKeyConstraint(["dispatch_id"], ["session_reminder_dispatches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subscription_id"], ["web_push_subscriptions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["exchange_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("delivery_id", name="uq_session_reminder_web_push_delivery_id"),
        sa.UniqueConstraint("event_id", "subscription_id", name="uq_session_reminder_web_push_event_subscription"),
    )
    op.create_index("ix_session_reminder_web_push_pending", "session_reminder_web_push_deliveries", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_session_reminder_web_push_pending", table_name="session_reminder_web_push_deliveries")
    op.drop_table("session_reminder_web_push_deliveries")
