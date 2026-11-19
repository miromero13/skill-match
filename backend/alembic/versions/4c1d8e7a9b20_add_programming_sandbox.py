"""Add versioned programming challenges and sandbox submissions.

Revision ID: 4c1d8e7a9b20
Revises: b7c79e2321a5
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "4c1d8e7a9b20"
down_revision = "b7c79e2321a5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "programming_challenges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("skill_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("skills.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("level_number", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=20), nullable=False, server_default="python"),
        sa.Column("starter_code", sa.Text(), nullable=False, server_default=""),
        sa.Column("time_limit_ms", sa.Integer(), nullable=False, server_default="2000"),
        sa.Column("memory_limit_mb", sa.Integer(), nullable=False, server_default="128"),
        sa.Column("max_output_bytes", sa.Integer(), nullable=False, server_default="65536"),
        sa.Column("allowed_imports", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("blocked_imports", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="DRAFT"),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("skill_id", "level_number", "version", name="uq_programming_challenge_version"),
        sa.CheckConstraint("language = 'python'", name="ck_programming_challenge_python"),
        sa.CheckConstraint("status IN ('DRAFT', 'PUBLISHED', 'ARCHIVED')", name="ck_programming_challenge_status"),
        sa.CheckConstraint("time_limit_ms BETWEEN 100 AND 30000", name="ck_programming_challenge_time_limit"),
        sa.CheckConstraint("memory_limit_mb BETWEEN 16 AND 1024", name="ck_programming_challenge_memory_limit"),
        sa.CheckConstraint("max_output_bytes BETWEEN 1024 AND 1048576", name="ck_programming_challenge_output_limit"),
    )
    op.create_index("ix_programming_challenges_skill_id", "programming_challenges", ["skill_id"])
    op.create_index("ix_programming_challenges_status", "programming_challenges", ["status"])
    op.create_index("ix_programming_challenges_published", "programming_challenges", ["skill_id", "level_number", "status"])

    op.create_table(
        "programming_test_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("challenge_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("programming_challenges.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("stdin_data", sa.Text(), nullable=False, server_default=""),
        sa.Column("expected_stdout", sa.Text(), nullable=False),
        sa.Column("visibility", sa.String(length=8), nullable=False, server_default="HIDDEN"),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("challenge_id", "order_index", name="uq_programming_test_order"),
        sa.CheckConstraint("visibility IN ('PUBLIC', 'HIDDEN')", name="ck_programming_test_visibility"),
    )
    op.create_index("ix_programming_test_cases_challenge_id", "programming_test_cases", ["challenge_id"])

    op.create_table(
        "programming_submissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("evaluation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("evaluations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("challenge_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("programming_challenges.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("passed_tests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("result", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_programming_submissions_evaluation_id", "programming_submissions", ["evaluation_id"])


def downgrade():
    op.drop_index("ix_programming_submissions_evaluation_id", table_name="programming_submissions")
    op.drop_table("programming_submissions")
    op.drop_index("ix_programming_test_cases_challenge_id", table_name="programming_test_cases")
    op.drop_table("programming_test_cases")
    op.drop_index("ix_programming_challenges_published", table_name="programming_challenges")
    op.drop_index("ix_programming_challenges_status", table_name="programming_challenges")
    op.drop_index("ix_programming_challenges_skill_id", table_name="programming_challenges")
    op.drop_table("programming_challenges")
