"""Limit programming challenges to canonical skill levels.

Revision ID: 5d2e9f7a1b34
Revises: 4c1d8e7a9b20
"""
from alembic import op

revision = "5d2e9f7a1b34"
down_revision = "4c1d8e7a9b20"
branch_labels = None
depends_on = None


def upgrade():
    op.create_check_constraint(
        "ck_programming_challenge_level",
        "programming_challenges",
        "level_number BETWEEN 1 AND 5",
    )


def downgrade():
    op.drop_constraint("ck_programming_challenge_level", "programming_challenges", type_="check")
