"""merge HU-38 and dev heads

Revision ID: c3bea441869b
Revises: aa38c7d9e102, bc43a710d962
Create Date: 2026-11-18 21:48:55.371003

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "c3bea441869b"
down_revision: str | Sequence[str] | None = ("aa38c7d9e102", "bc43a710d962")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""


def downgrade() -> None:
    """Downgrade schema."""
