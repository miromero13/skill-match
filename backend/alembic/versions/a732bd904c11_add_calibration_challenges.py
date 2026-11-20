"""Add short-lived calibration challenges without changing exam attempts."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a732bd904c11"
down_revision = "99731898af88"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "evaluation_calibration_challenges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("evaluation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("evaluations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("enrollment_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checks", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_evaluation_calibration_challenges_evaluation_id", "evaluation_calibration_challenges", ["evaluation_id"])


def downgrade():
    op.drop_index("ix_evaluation_calibration_challenges_evaluation_id", table_name="evaluation_calibration_challenges")
    op.drop_table("evaluation_calibration_challenges")
