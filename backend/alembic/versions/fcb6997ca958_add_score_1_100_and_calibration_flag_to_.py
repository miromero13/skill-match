"""add score_1_100 and calibration flag to validation_results

Revision ID: fcb6997ca958
Revises: 655037c2b8ad
Create Date: 2026-11-17 11:46:53.984050

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'fcb6997ca958'
down_revision: Union[str, Sequence[str], None] = '655037c2b8ad'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Existing rows are backfilled through a temporary server default (1.0 / false) so the
    NOT NULL columns can be added safely; the default is then dropped to match the ORM model.
    """
    op.add_column(
        'validation_results',
        sa.Column('puntaje_1_100', sa.Float(), nullable=False, server_default=sa.text('1.0')),
    )
    op.add_column(
        'validation_results',
        sa.Column('puntaje_calibrado', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column('validation_results', 'puntaje_1_100', server_default=None)
    op.alter_column('validation_results', 'puntaje_calibrado', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('validation_results', 'puntaje_calibrado')
    op.drop_column('validation_results', 'puntaje_1_100')
