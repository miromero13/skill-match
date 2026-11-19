"""Persist explicit text consent and rubric grading provenance/results.

Revision ID: f6a39d2c801b
Revises: e349ca32f396
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f6a39d2c801b"
down_revision = "e349ca32f396"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("theory_exams", sa.Column("text_consent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("theory_exams", sa.Column("grading_provider", sa.String(16), nullable=True))
    op.add_column("theory_exams", sa.Column("grading_model", sa.String(120), nullable=True))
    op.add_column("theory_exams", sa.Column("grading_prompt_version", sa.String(32), nullable=True))
    op.add_column("theory_exams", sa.Column("grading_state", sa.String(16), server_default="PENDING", nullable=False))
    op.add_column("theory_exams", sa.Column("grading_result", postgresql.JSONB(), nullable=True))
    op.add_column("theory_exams", sa.Column("grading_score", sa.Float(), nullable=True))
    op.add_column("theory_exams", sa.Column("grading_error", sa.String(64), nullable=True))


def downgrade():
    for name in ("grading_error", "grading_score", "grading_result", "grading_state", "grading_prompt_version",
                 "grading_model", "grading_provider", "text_consent_at"):
        op.drop_column("theory_exams", name)
