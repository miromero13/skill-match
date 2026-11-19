"""Store the enrolled voiceprint per trial.

Revision ID: e5b1c7d3a962
Revises: c4e8a1f27b95
"""
from alembic import op
import sqlalchemy as sa

revision = "e5b1c7d3a962"
down_revision = "c4e8a1f27b95"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("browser_supervision_trials", sa.Column("voiceprint", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("browser_supervision_trials", "voiceprint")
