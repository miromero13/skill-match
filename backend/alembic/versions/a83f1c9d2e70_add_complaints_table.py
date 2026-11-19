"""add_complaints_table

Revision ID: a83f1c9d2e70
Revises: e42a91b8c350, f3a8d2c19e47
Create Date: 2026-11-19 12:54:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a83f1c9d2e70'
down_revision: Union[str, Sequence[str], None] = ('e42a91b8c350', 'f3a8d2c19e47')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'complaints',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('exchange_sessions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('reason', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=150), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('evidence_urls', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='OPEN'),
        sa.Column('admin_response', sa.Text(), nullable=True),
        sa.Column('points_compensated', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('resolved_by_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('points_compensated >= 0', name='ck_complaint_nonnegative_compensation'),
        sa.CheckConstraint("status IN ('OPEN', 'RESOLVED', 'DISMISSED')", name='ck_complaint_status_valid'),
    )
    op.create_index('ix_complaints_user_id', 'complaints', ['user_id'])
    op.create_index('ix_complaints_session_id', 'complaints', ['session_id'])
    op.create_index('ix_complaints_status', 'complaints', ['status'])
    op.create_index('ix_complaints_user_status', 'complaints', ['user_id', 'status'])
    op.create_index('ix_complaints_status_created', 'complaints', ['status', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_complaints_status_created', table_name='complaints')
    op.drop_index('ix_complaints_user_status', table_name='complaints')
    op.drop_index('ix_complaints_status', table_name='complaints')
    op.drop_index('ix_complaints_session_id', table_name='complaints')
    op.drop_index('ix_complaints_user_id', table_name='complaints')
    op.drop_table('complaints')
