"""Store what a passed calibration gives supervision: gaze zone, voiceprint and occlusion reference.

Revision ID: f3a8d2c19e47
Revises: e5b1c7d3a962
"""
from alembic import op
import sqlalchemy as sa

revision = "f3a8d2c19e47"
down_revision = "e5b1c7d3a962"
branch_labels = None
depends_on = None

TABLE = "evaluation_calibration_challenges"
COLUMNS = ("gaze_zone", "voiceprint", "occlusion_ref")


def upgrade():
    # Nullable: challenges that never passed (and every pre-existing row) have none of them.
    for name in COLUMNS:
        op.add_column(TABLE, sa.Column(name, sa.JSON(), nullable=True))


def downgrade():
    for name in reversed(COLUMNS):
        op.drop_column(TABLE, name)
