"""add identity verification to users

Revision ID: f81b2c3d4e5f
Revises: 006744e724ff
Create Date: 2026-11-17 22:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f81b2c3d4e5f'
down_revision: Union[str, Sequence[str], None] = '006744e724ff'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: agregar columnas de verificación de identidad con CI/DNI."""
    op.add_column(
        'users',
        sa.Column(
            'identity_status',
            sa.String(length=32),
            nullable=False,
            server_default='NOT_VERIFIED',
            comment='Estado de verificación de identidad: NOT_VERIFIED, VERIFIED, REJECTED',
        )
    )
    op.add_column(
        'users',
        sa.Column(
            'id_document_number',
            sa.String(length=64),
            nullable=True,
            comment='Número de carnet de identidad o DNI verificado',
        )
    )
    op.add_column(
        'users',
        sa.Column(
            'id_document_type',
            sa.String(length=32),
            nullable=True,
            server_default='CI',
            comment='Tipo de documento de identidad oficial (CI/DNI)',
        )
    )
    op.add_column(
        'users',
        sa.Column(
            'id_face_similarity_score',
            sa.Float(),
            nullable=True,
            comment='Puntaje de similitud coseno entre foto del carnet y rostro en vivo (0.0 a 1.0)',
        )
    )
    op.add_column(
        'users',
        sa.Column(
            'identity_verified_at',
            sa.DateTime(timezone=True),
            nullable=True,
            comment='Marca de tiempo UTC de la verificación exitosa de identidad',
        )
    )
    op.add_column(
        'users',
        sa.Column(
            'identity_rejection_reason',
            sa.String(length=255),
            nullable=True,
            comment='Motivo explicativo en caso de rechazo de identidad',
        )
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'identity_rejection_reason')
    op.drop_column('users', 'identity_verified_at')
    op.drop_column('users', 'id_face_similarity_score')
    op.drop_column('users', 'id_document_type')
    op.drop_column('users', 'id_document_number')
    op.drop_column('users', 'identity_status')
