"""Add user blocks and moderation reports (HU-26 / RF-MAT-14, RF-NOT-06).

Revision ID: b34c56d7e892
Revises: a23b21c4e591
Create Date: 2026-11-17 11:25:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "b34c56d7e892"
down_revision = "a23b21c4e591"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Tabla de Bloqueos Preventivos Bilaterales (RF-MAT-14)
    op.create_table(
        "user_blocks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("blocker_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("blocked_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reason", sa.String(length=100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("blocker_id", "blocked_id", name="uq_user_blocks_blocker_blocked"),
        sa.CheckConstraint("blocker_id != blocked_id", name="ck_user_blocks_no_self_block"),
    )
    op.create_index("ix_user_blocks_id", "user_blocks", ["id"])
    op.create_index("ix_user_blocks_blocker_id", "user_blocks", ["blocker_id"])
    op.create_index("ix_user_blocks_blocked_id", "user_blocks", ["blocked_id"])

    # 2. Tabla de Reportes a Moderación Administrativa (RF-NOT-06)
    op.create_table(
        "user_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("reporter_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reported_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reason", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("evidence_url", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="PENDING"),
        sa.Column("admin_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("reporter_id != reported_id", name="ck_user_reports_no_self_report"),
    )
    op.create_index("ix_user_reports_id", "user_reports", ["id"])
    op.create_index("ix_user_reports_reporter_id", "user_reports", ["reporter_id"])
    op.create_index("ix_user_reports_reported_id", "user_reports", ["reported_id"])
    op.create_index("ix_user_reports_reason", "user_reports", ["reason"])
    op.create_index("ix_user_reports_status", "user_reports", ["status"])


def downgrade() -> None:
    op.drop_index("ix_user_reports_status", table_name="user_reports")
    op.drop_index("ix_user_reports_reason", table_name="user_reports")
    op.drop_index("ix_user_reports_reported_id", table_name="user_reports")
    op.drop_index("ix_user_reports_reporter_id", table_name="user_reports")
    op.drop_index("ix_user_reports_id", table_name="user_reports")
    op.drop_table("user_reports")

    op.drop_index("ix_user_blocks_blocked_id", table_name="user_blocks")
    op.drop_index("ix_user_blocks_blocker_id", table_name="user_blocks")
    op.drop_index("ix_user_blocks_id", table_name="user_blocks")
    op.drop_table("user_blocks")
