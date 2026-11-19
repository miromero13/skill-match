"""fusionar cabezas

Revision ID: 2776e88fdc6e
Revises: f74e31b8a954, fcb6997ca958
Create Date: 2026-11-17 22:37:40.358784

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2776e88fdc6e'
down_revision: Union[str, Sequence[str], None] = ('f74e31b8a954', 'fcb6997ca958')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
