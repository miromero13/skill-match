"""Add check constraint for teaching skill rate consistency (HU-14).

Revision ID: f74e31b8a954
Revises: e63f20a9c143
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f74e31b8a954"
down_revision: Union[str, Sequence[str], None] = "e63f20a9c143"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_teaching_rate",
        "user_teaching_skills",
        "(accepts_points = true AND hourly_points_rate > 0 AND hourly_points_rate IS NOT NULL) OR (accepts_points = false AND hourly_points_rate IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_teaching_rate", "user_teaching_skills", type_="check")
