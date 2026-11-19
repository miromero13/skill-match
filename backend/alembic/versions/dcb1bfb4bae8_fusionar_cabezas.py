"""fusionar cabezas

Revision ID: dcb1bfb4bae8
Revises: bdec2255b108, d351316e7e21
Create Date: 2026-11-19 16:52:26.706605

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dcb1bfb4bae8'
down_revision: Union[str, Sequence[str], None] = ('bdec2255b108', 'd351316e7e21')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
