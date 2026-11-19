"""Merge the open heads and track the last audiovisual window per trial.

c3bea441869b is the head that carries the browser-supervision tables.

Revision ID: dbe2f44f08c2
Revises: c3bea441869b, ce51f995031a, f6a39d2c801b
"""
from alembic import op
import sqlalchemy as sa

revision = "dbe2f44f08c2"
down_revision = ("c3bea441869b", "ce51f995031a", "f6a39d2c801b")
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("browser_supervision_trials", sa.Column("last_av_window_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("browser_supervision_trials", "last_av_window_at")
