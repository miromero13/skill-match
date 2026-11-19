"""Add theory answer receipts and per-question server timing, without raw media.

Revision ID: e349ca32f396
Revises: d239b921e285
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e349ca32f396"
down_revision = "d239b921e285"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("theory_exams", sa.Column("current_position", sa.Integer(), server_default="0", nullable=False))
    op.add_column("theory_exams", sa.Column("question_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("theory_exams", sa.Column("answers", postgresql.JSONB(), server_default="[]", nullable=False))


def downgrade():
    op.drop_column("theory_exams", "answers")
    op.drop_column("theory_exams", "question_started_at")
    op.drop_column("theory_exams", "current_position")
