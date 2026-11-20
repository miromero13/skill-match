"""add device push tokens

Revision ID: eae2652e438a
Revises: dcb1bfb4bae8
Create Date: 2026-11-19 22:57:23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'eae2652e438a'
down_revision: Union[str, Sequence[str], None] = 'dcb1bfb4bae8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "device_push_tokens",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("fcm_token", sa.String(length=512), nullable=False),
        sa.Column("platform", sa.String(length=20), nullable=False, server_default=sa.text("'android'")),
        sa.Column("device_label", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_device_push_tokens_user_id", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fcm_token", name="uq_device_push_tokens_fcm_token"),
    )
    op.create_index(
        "ix_device_push_tokens_user_active",
        "device_push_tokens",
        ["user_id", "is_active"],
    )


def downgrade() -> None:
    op.drop_index("ix_device_push_tokens_user_active", table_name="device_push_tokens")
    op.drop_table("device_push_tokens")
