"""Merge the current dev heads before HU-38.

Revision ID: c38a1e2f4b60
Revises: f74e31b8a954, fcb6997ca958
"""

from collections.abc import Sequence

revision: str = "c38a1e2f4b60"
down_revision: str | Sequence[str] | None = ("f74e31b8a954", "fcb6997ca958")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
