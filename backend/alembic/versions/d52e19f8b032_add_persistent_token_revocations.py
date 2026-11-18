"""Add a shared, durable JWT denylist.

Revision ID: d52e19f8b032
Revises: c41d08e7a921
"""
from alembic import op
import sqlalchemy as sa

revision = "d52e19f8b032"
down_revision = "c41d08e7a921"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "revoked_tokens",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_revoked_tokens_expires_at", "revoked_tokens", ["expires_at"])


def downgrade():
    op.drop_table("revoked_tokens")
