"""Add shared evaluation preflight without consuming attempts.

Revision ID: 9b742e18ac30
Revises: 006744e724ff
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "9b742e18ac30"
down_revision = "006744e724ff"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "evaluations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("skill_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("skills.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("teaching_skill_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user_teaching_skills.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("biometric_consent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("policy_version", sa.String(20), nullable=False),
        sa.Column("ip_address", sa.String(64), nullable=False),
        sa.Column("user_agent", sa.String(512), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "skill_id", name="uq_evaluation_free_skill"),
    )
    op.create_index("ix_evaluations_user_id", "evaluations", ["user_id"])


def downgrade():
    op.drop_index("ix_evaluations_user_id", table_name="evaluations")
    op.drop_table("evaluations")
