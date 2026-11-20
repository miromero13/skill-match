"""add defense and final evaluation fields

Revision ID: a9c4e1f2d801
Revises: dcb1bfb4bae8
Create Date: 2026-11-20 08:17:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a9c4e1f2d801"
down_revision = "dcb1bfb4bae8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("evaluations", sa.Column("final_score", sa.Float(), nullable=True))
    op.add_column("evaluations", sa.Column("final_summary", sa.JSON(), nullable=True))
    op.add_column("challenge_submissions", sa.Column("defense_submission_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("challenge_submissions", sa.Column("defense_transcript", sa.Text(), nullable=True))
    op.add_column("challenge_submissions", sa.Column("defense_score", sa.Float(), nullable=True))
    op.add_column("challenge_submissions", sa.Column("defense_feedback", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("challenge_submissions", "defense_feedback")
    op.drop_column("challenge_submissions", "defense_score")
    op.drop_column("challenge_submissions", "defense_transcript")
    op.drop_column("challenge_submissions", "defense_submission_id")
    op.drop_column("evaluations", "final_summary")
    op.drop_column("evaluations", "final_score")
