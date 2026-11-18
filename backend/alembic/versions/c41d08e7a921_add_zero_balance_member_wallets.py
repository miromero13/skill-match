"""Add real member wallets without granting an opening bonus.

Revision ID: c41d08e7a921
Revises: b34c56d7e892
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c41d08e7a921"
down_revision = "b34c56d7e892"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "wallets",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("balance", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("balance >= 0", name="ck_wallet_nonnegative_balance"),
    )
    op.execute("INSERT INTO wallets (user_id, balance) SELECT id, 0 FROM users WHERE role = 'MEMBER'")


def downgrade():
    op.drop_table("wallets")
