"""Add versioned theory question drafts without inserting application records.

Revision ID: c139a820f174
Revises: bc43a710d962
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c139a820f174"
down_revision = "bc43a710d962"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "theory_question_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("skill_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("level_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("content", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", "version"),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("version >= 1", name="ck_theory_question_version"),
        sa.CheckConstraint("level_number BETWEEN 1 AND 5", name="ck_theory_question_level"),
        sa.CheckConstraint("status IN ('DRAFT', 'PUBLISHED', 'ARCHIVED')", name="ck_theory_question_status"),
    )
    op.create_index("ix_theory_question_revisions_skill_id", "theory_question_revisions", ["skill_id"])


def downgrade():
    op.drop_index("ix_theory_question_revisions_skill_id", table_name="theory_question_revisions")
    op.drop_table("theory_question_revisions")
