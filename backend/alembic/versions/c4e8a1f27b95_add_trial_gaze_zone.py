"""Store the calibrated screen gaze zone per trial.

Revision ID: c4e8a1f27b95
Revises: dbe2f44f08c2
"""
from alembic import op
import sqlalchemy as sa

revision = "c4e8a1f27b95"
down_revision = "dbe2f44f08c2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("browser_supervision_trials", sa.Column("gaze_zone", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("browser_supervision_trials", "gaze_zone")
