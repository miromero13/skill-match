"""fusionar cabezas

Revision ID: 006744e724ff
Revises: 2776e88fdc6e
Create Date: 2026-11-17 22:37:47.177960

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '006744e724ff'
down_revision: Union[str, Sequence[str], None] = '2776e88fdc6e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
