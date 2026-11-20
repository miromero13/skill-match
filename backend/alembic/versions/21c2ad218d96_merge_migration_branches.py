"""merge migration branches

Revision ID: 21c2ad218d96
Revises: aee6338bcbf9
Create Date: 2026-11-20 11:35:44.000936

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '21c2ad218d96'
down_revision: Union[str, Sequence[str], None] = 'aee6338bcbf9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
