"""Generalize programming challenges into reusable evaluation challenges.

Revision ID: 6e3f0a8b2c45
Revises: 5d2e9f7a1b34
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "6e3f0a8b2c45"
down_revision = "5d2e9f7a1b34"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("ck_programming_challenge_python", "programming_challenges", type_="check")
    op.rename_table("programming_challenges", "challenges")
    op.rename_table("programming_test_cases", "challenge_test_cases")
    op.rename_table("programming_submissions", "challenge_submissions")
    op.alter_column("challenges", "language", new_column_name="execution_profile")
    op.execute("UPDATE challenges SET execution_profile = 'PYTHON_3_12' WHERE execution_profile = 'python'")
    op.alter_column("challenges", "execution_profile", type_=sa.String(length=40), existing_type=sa.String(length=20), nullable=False)
    op.add_column("challenges", sa.Column("evaluation_modality", sa.String(length=24), nullable=False, server_default="SANDBOX"))
    op.add_column("challenges", sa.Column("challenge_type_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_challenges_challenge_type_id",
        "challenges",
        "challenge_types",
        ["challenge_type_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_challenges_challenge_type_id", "challenges", ["challenge_type_id"])
    op.create_check_constraint("ck_challenge_modality", "challenges", "evaluation_modality IN ('SANDBOX', 'SPREADSHEET')")
    op.create_check_constraint("ck_challenge_profile", "challenges", "execution_profile <> ''")

    # Keep database names aligned with the generic ORM contract.
    op.execute("ALTER TABLE challenges RENAME CONSTRAINT uq_programming_challenge_version TO uq_challenge_version")
    op.execute("ALTER TABLE challenges RENAME CONSTRAINT ck_programming_challenge_status TO ck_challenge_status")
    op.execute("ALTER TABLE challenges RENAME CONSTRAINT ck_programming_challenge_level TO ck_challenge_level")
    op.execute("ALTER TABLE challenges RENAME CONSTRAINT ck_programming_challenge_time_limit TO ck_challenge_time_limit")
    op.execute("ALTER TABLE challenges RENAME CONSTRAINT ck_programming_challenge_memory_limit TO ck_challenge_memory_limit")
    op.execute("ALTER TABLE challenges RENAME CONSTRAINT ck_programming_challenge_output_limit TO ck_challenge_output_limit")
    op.execute("ALTER TABLE challenge_test_cases RENAME CONSTRAINT uq_programming_test_order TO uq_challenge_test_order")
    op.execute("ALTER TABLE challenge_test_cases RENAME CONSTRAINT ck_programming_test_visibility TO ck_challenge_test_visibility")


def downgrade():
    op.drop_constraint("ck_challenge_profile", "challenges", type_="check")
    op.drop_constraint("ck_challenge_modality", "challenges", type_="check")
    op.drop_index("ix_challenges_challenge_type_id", table_name="challenges")
    op.drop_constraint("fk_challenges_challenge_type_id", "challenges", type_="foreignkey")
    op.drop_column("challenges", "challenge_type_id")
    op.drop_column("challenges", "evaluation_modality")
    op.alter_column("challenges", "execution_profile", new_column_name="language")
    op.rename_table("challenge_submissions", "programming_submissions")
    op.rename_table("challenge_test_cases", "programming_test_cases")
    op.rename_table("challenges", "programming_challenges")
