"""fusionar cabezas

Revision ID: 99731898af88
Revises: 9b742e18ac30, f81b2c3d4e5f
Create Date: 2026-11-17 23:03:15.475498

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '99731898af88'
down_revision: Union[str, Sequence[str], None] = ('9b742e18ac30', 'f81b2c3d4e5f')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
