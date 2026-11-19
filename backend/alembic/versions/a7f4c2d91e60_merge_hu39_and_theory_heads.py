"""Merge HU-39 session completion and theory grading heads.

Revision ID: a7f4c2d91e60
Revises: d49e1f5a8b72, f6a39d2c801b
Create Date: 2026-11-19 02:00:00.000000
"""

from collections.abc import Sequence


# revision identifiers, used by Alembic.
revision: str = "a7f4c2d91e60"
down_revision: str | Sequence[str] | None = (
    "d49e1f5a8b72",
    "f6a39d2c801b",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Join both already-applied schema branches without extra operations."""


def downgrade() -> None:
    """Return to the two independent migration heads."""
