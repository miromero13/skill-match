"""fusionar cabezas

Revision ID: bdec2255b108
Revises: 6e3f0a8b2c45
Create Date: 2026-11-19 11:28:02.230152

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bdec2255b108'
down_revision: Union[str, Sequence[str], None] = '6e3f0a8b2c45'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
