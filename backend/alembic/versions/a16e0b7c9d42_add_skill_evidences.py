"""Add external evidence for teaching skills.

Revision ID: a16e0b7c9d42
Revises: f69de0a4b8f0
"""

from alembic import op
import sqlalchemy as sa

revision: str = "a16e0b7c9d42"
down_revision: str = "f69de0a4b8f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "skill_evidences",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("teaching_skill_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(150), nullable=False),
        sa.Column("description", sa.String(2000), nullable=True),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("evidence_type", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["teaching_skill_id"], ["user_teaching_skills.id"],
            ondelete="CASCADE", name="fk_skill_evidences_teaching_skill_id",
        ),
        sa.UniqueConstraint("teaching_skill_id", "url", name="uq_skill_evidences_skill_url"),
        sa.CheckConstraint(
            "evidence_type IN ('REPOSITORY', 'VIDEO', 'CERTIFICATE', 'OTHER')",
            name="ck_skill_evidences_type",
        ),
        sa.CheckConstraint("length(btrim(title)) > 0", name="ck_skill_evidences_title"),
        sa.CheckConstraint(
            "url LIKE 'http://%' OR url LIKE 'https://%'",
            name="ck_skill_evidences_url_scheme",
        ),
    )
    op.create_index("ix_skill_evidences_teaching_skill_id", "skill_evidences", ["teaching_skill_id"])


def downgrade() -> None:
    op.drop_index("ix_skill_evidences_teaching_skill_id", table_name="skill_evidences")
    op.drop_table("skill_evidences")
