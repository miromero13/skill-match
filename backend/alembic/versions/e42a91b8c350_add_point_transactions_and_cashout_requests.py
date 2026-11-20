"""add_point_transactions_and_cashout_requests

Revision ID: e42a91b8c350
Revises: 6e3f0a8b2c45, a7f4c2d91e60
Create Date: 2026-11-19 10:02:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e42a91b8c350'
down_revision: Union[str, Sequence[str], None] = ('6e3f0a8b2c45', 'a7f4c2d91e60')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Columna escrow_balance en wallets
    op.add_column(
        'wallets',
        sa.Column('escrow_balance', sa.Integer(), nullable=False, server_default='0')
    )
    op.create_check_constraint(
        'ck_wallet_nonnegative_escrow',
        'wallets',
        'escrow_balance >= 0'
    )

    # 2. Tabla point_transactions
    op.create_table(
        'point_transactions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('balance_after', sa.Integer(), nullable=False),
        sa.Column('escrow_after', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('transaction_type', sa.String(length=30), nullable=False),
        sa.Column('reference_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('description', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(
            "transaction_type IN ('TOPUP', 'CLASS_PAYMENT', 'TIP', 'CASHOUT', 'ADMIN_REWARD')",
            name='ck_point_transactions_type'
        )
    )
    op.create_index('ix_point_transactions_user_id', 'point_transactions', ['user_id'])
    op.create_index('ix_point_transactions_type', 'point_transactions', ['transaction_type'])
    op.create_index('ix_point_transactions_reference_id', 'point_transactions', ['reference_id'])
    op.create_index('ix_point_transactions_user_created', 'point_transactions', ['user_id', 'created_at'])

    # 3. Tabla cashout_requests
    op.create_table(
        'cashout_requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('points_amount', sa.Integer(), nullable=False),
        sa.Column('gross_amount_usd', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('fee_percentage', sa.Numeric(precision=5, scale=2), nullable=False, server_default='15.00'),
        sa.Column('fee_amount_usd', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('net_amount_usd', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='PENDING'),
        sa.Column('bank_name', sa.String(length=100), nullable=False),
        sa.Column('account_number', sa.String(length=100), nullable=False),
        sa.Column('account_holder_name', sa.String(length=150), nullable=False),
        sa.Column('account_holder_id', sa.String(length=50), nullable=False),
        sa.Column('admin_notes', sa.String(length=500), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('points_amount >= 10', name='ck_cashout_requests_min_points'),
        sa.CheckConstraint("status IN ('PENDING', 'APPROVED', 'REJECTED')", name='ck_cashout_requests_status'),
        sa.CheckConstraint('net_amount_usd >= 0', name='ck_cashout_requests_net_positive')
    )
    op.create_index('ix_cashout_requests_user_id', 'cashout_requests', ['user_id'])
    op.create_index('ix_cashout_requests_status', 'cashout_requests', ['status'])
    op.create_index('ix_cashout_requests_user_status', 'cashout_requests', ['user_id', 'status'])


def downgrade() -> None:
    op.drop_table('cashout_requests')
    op.drop_table('point_transactions')
    op.drop_constraint('ck_wallet_nonnegative_escrow', 'wallets', type_='check')
    op.drop_column('wallets', 'escrow_balance')
