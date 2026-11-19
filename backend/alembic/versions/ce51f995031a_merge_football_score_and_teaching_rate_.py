"""merge football score and teaching rate constraint heads

Revision ID: ce51f995031a
Revises: fcb6997ca958, f74e31b8a954
Create Date: 2026-11-17 23:09:51.457367

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ce51f995031a'
down_revision: Union[str, Sequence[str], None] = ('fcb6997ca958', 'f74e31b8a954')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
