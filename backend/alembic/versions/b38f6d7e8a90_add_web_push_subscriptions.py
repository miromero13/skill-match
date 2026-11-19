"""Add private Web Push device subscriptions for HU-38.

Revision ID: b38f6d7e8a90
Revises: a38e7c9d1f04
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b38f6d7e8a90"
down_revision: str | None = "a38e7c9d1f04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "web_push_subscriptions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("endpoint", sa.String(length=2048), nullable=False),
        sa.Column("endpoint_hash", sa.String(length=64), nullable=False),
        sa.Column("p256dh", sa.String(length=4096), nullable=False),
        sa.Column("auth", sa.String(length=1024), nullable=False),
        sa.Column("device_label", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_web_push_subscriptions_user_id", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "endpoint_hash", name="uq_web_push_subscriptions_endpoint_hash",
        ),
    )
    op.create_index(
        "ix_web_push_subscriptions_user_active",
        "web_push_subscriptions",
        ["user_id", "is_active"],
    )
    op.create_index(
        "ix_web_push_subscriptions_active_updated",
        "web_push_subscriptions",
        ["updated_at"],
        postgresql_where=sa.text("is_active IS true"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_web_push_subscriptions_active_updated",
        table_name="web_push_subscriptions",
    )
    op.drop_index(
        "ix_web_push_subscriptions_user_active",
        table_name="web_push_subscriptions",
    )
    op.drop_table("web_push_subscriptions")
