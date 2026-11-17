"""add latitude and longitude to users

Revision ID: 80fd533f1c18
Revises: d25e4f6a7b8c
Create Date: 2026-11-16 22:08:03.904748

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '80fd533f1c18'
down_revision: Union[str, Sequence[str], None] = 'd25e4f6a7b8c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("users", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("users", sa.Column("longitude", sa.Float(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "longitude")
    op.drop_column("users", "latitude")
