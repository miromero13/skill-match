"""Persist fixed theory exam snapshots at the actual attempt start.

Revision ID: d239b921e285
Revises: c139a820f174
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d239b921e285"
down_revision = "c139a820f174"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "theory_exams",
        sa.Column("evaluation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("level_number", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("questions", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("evaluation_id"),
        sa.ForeignKeyConstraint(["evaluation_id"], ["evaluations.id"], ondelete="RESTRICT"),
    )


def downgrade():
    op.drop_table("theory_exams")
