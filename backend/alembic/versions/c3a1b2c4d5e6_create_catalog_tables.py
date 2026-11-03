"""Create admin catalog tables."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c3a1b2c4d5e6"
down_revision: Union[str, Sequence[str], None] = "703cb8063726"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_categories_slug", "categories", ["slug"], unique=True)
    op.create_table(
        "challenge_types",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("evaluation_modality", sa.String(50), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_challenge_types_code", "challenge_types", ["code"], unique=True)
    op.create_table(
        "skills",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("category_id", sa.UUID(), nullable=False),
        sa.Column("challenge_type_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("slug", sa.String(170), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("min_approval_threshold", sa.Float(), nullable=False),
        sa.Column("is_ready_to_publish", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["challenge_type_id"], ["challenge_types.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_skills_slug", "skills", ["slug"], unique=True)
    op.create_table(
        "skill_levels",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("skill_id", sa.UUID(), nullable=False),
        sa.Column("level_number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("skill_id", "level_number", name="uq_skill_levels_skill_level"),
    )
    op.create_table(
        "rubrics",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("skill_level_id", sa.UUID(), nullable=False),
        sa.Column("instructions", sa.String(), nullable=True),
        sa.Column("min_score", sa.Float(), nullable=False),
        sa.Column("criteria", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["skill_level_id"], ["skill_levels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("skill_level_id"),
    )


def downgrade() -> None:
    op.drop_table("rubrics")
    op.drop_table("skill_levels")
    op.drop_index("ix_skills_slug", table_name="skills")
    op.drop_table("skills")
    op.drop_index("ix_challenge_types_code", table_name="challenge_types")
    op.drop_table("challenge_types")
    op.drop_index("ix_categories_slug", table_name="categories")
    op.drop_table("categories")
