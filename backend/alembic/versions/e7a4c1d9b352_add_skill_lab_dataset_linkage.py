"""Link dataset samples and model versions to catalog skills (skill lab).

Additive only: new nullable columns (``sample_role`` has a server default), foreign keys,
indexes and a relaxed ``file_format`` check (adds webm/mov). Existing rows are not rewritten.

Revision ID: e7a4c1d9b352
Revises: dcb1bfb4bae8
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "e7a4c1d9b352"
down_revision: str = "dcb1bfb4bae8"
branch_labels = None
depends_on = None

FORMAT_CHECK = "ck_dataset_samples_format"
OLD_FORMATS = "file_format IN ('mp4', 'wav', 'py')"
NEW_FORMATS = "file_format IN ('mp4', 'wav', 'py', 'webm', 'mov')"


def upgrade() -> None:
    op.add_column("dataset_samples", sa.Column("skill_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("dataset_samples", sa.Column("skill_level_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("dataset_samples", sa.Column("criterion_key", sa.String(length=64), nullable=True))
    op.add_column(
        "dataset_samples",
        sa.Column("sample_role", sa.String(length=20), nullable=False, server_default="TRAINING"),
    )
    op.add_column("dataset_samples", sa.Column("analysis", sa.JSON(), nullable=True))
    op.create_foreign_key(
        "fk_dataset_samples_skill_id", "dataset_samples", "skills", ["skill_id"], ["id"], ondelete="SET NULL"
    )
    op.create_foreign_key(
        "fk_dataset_samples_skill_level_id", "dataset_samples", "skill_levels",
        ["skill_level_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_dataset_samples_skill_id", "dataset_samples", ["skill_id"])
    op.create_index("ix_dataset_samples_skill_level_id", "dataset_samples", ["skill_level_id"])
    op.create_check_constraint(
        "ck_dataset_samples_sample_role", "dataset_samples", "sample_role IN ('TRAINING', 'REFERENCE')"
    )
    op.drop_constraint(FORMAT_CHECK, "dataset_samples", type_="check")
    op.create_check_constraint(FORMAT_CHECK, "dataset_samples", NEW_FORMATS)

    op.add_column("model_versions", sa.Column("skill_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_model_versions_skill_id", "model_versions", "skills", ["skill_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index("ix_model_versions_skill_id", "model_versions", ["skill_id"])
    # One active per-skill validator; rows without skill (football/flute globals) are unaffected.
    op.create_index(
        "uq_model_versions_active_skill", "model_versions", ["skill_id"], unique=True,
        postgresql_where=sa.text("activa IS TRUE AND skill_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_model_versions_active_skill", table_name="model_versions")
    op.drop_index("ix_model_versions_skill_id", table_name="model_versions")
    op.drop_constraint("fk_model_versions_skill_id", "model_versions", type_="foreignkey")
    op.drop_column("model_versions", "skill_id")

    op.drop_constraint(FORMAT_CHECK, "dataset_samples", type_="check")
    # NOT VALID keeps the downgrade non-destructive if webm/mov samples were uploaded meanwhile;
    # new rows are still checked against the original formats.
    op.execute(f"ALTER TABLE dataset_samples ADD CONSTRAINT {FORMAT_CHECK} CHECK ({OLD_FORMATS}) NOT VALID")
    op.drop_constraint("ck_dataset_samples_sample_role", "dataset_samples", type_="check")
    op.drop_index("ix_dataset_samples_skill_level_id", table_name="dataset_samples")
    op.drop_index("ix_dataset_samples_skill_id", table_name="dataset_samples")
    op.drop_constraint("fk_dataset_samples_skill_level_id", "dataset_samples", type_="foreignkey")
    op.drop_constraint("fk_dataset_samples_skill_id", "dataset_samples", type_="foreignkey")
    op.drop_column("dataset_samples", "analysis")
    op.drop_column("dataset_samples", "sample_role")
    op.drop_column("dataset_samples", "criterion_key")
    op.drop_column("dataset_samples", "skill_level_id")
    op.drop_column("dataset_samples", "skill_id")
