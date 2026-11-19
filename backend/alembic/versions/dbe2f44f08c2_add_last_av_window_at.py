"""Track the last audiovisual window per trial.

Revision ID: dbe2f44f08c2
Revises: a7c19e3b5d20
"""
from alembic import op
import sqlalchemy as sa

revision = "dbe2f44f08c2"
down_revision = "a7c19e3b5d20"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("browser_supervision_trials", sa.Column("last_av_window_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("browser_supervision_trials", "last_av_window_at")
