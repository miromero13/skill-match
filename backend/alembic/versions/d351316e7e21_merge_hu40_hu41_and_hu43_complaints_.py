"""merge hu40_hu41 and hu43 complaints heads

Revision ID: d351316e7e21
Revises: 4654c5a87305, a83f1c9d2e70
Create Date: 2026-11-19 16:12:26.392365

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd351316e7e21'
down_revision: Union[str, Sequence[str], None] = ('4654c5a87305', 'a83f1c9d2e70')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
