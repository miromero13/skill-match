"""merge football and profile heads

Revision ID: 655037c2b8ad
Revises: c49f2d8e6b10, d25e4f6a7b8c
Create Date: 2026-11-16 23:02:28.487669

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '655037c2b8ad'
down_revision: Union[str, Sequence[str], None] = ('c49f2d8e6b10', 'd25e4f6a7b8c')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
