"""fusionar cabezas

Revision ID: b7c79e2321a5
Revises: c3bea441869b, f6a39d2c801b
Create Date: 2026-11-18 23:57:08.597307

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7c79e2321a5'
down_revision: Union[str, Sequence[str], None] = ('c3bea441869b', 'f6a39d2c801b')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
