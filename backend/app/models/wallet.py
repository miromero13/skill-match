"""SkillPoints Wallet, Transactions and Cashout Requests (HU-42 / RF-SES-09 / RF-WAL-01 / RF-WAL-02)."""
from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class PointTransactionType(str, Enum):
    TOPUP = "TOPUP"
    CLASS_PAYMENT = "CLASS_PAYMENT"
    TIP = "TIP"
    CASHOUT = "CASHOUT"
    ADMIN_REWARD = "ADMIN_REWARD"


class CashoutStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class Wallet(Base, TimestampMixin):
    __tablename__ = "wallets"
    __table_args__ = (
        CheckConstraint("balance >= 0", name="ck_wallet_nonnegative_balance"),
        CheckConstraint("escrow_balance >= 0", name="ck_wallet_nonnegative_escrow"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    escrow_balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


class PointTransaction(Base, TimestampMixin):
    __tablename__ = "point_transactions"
    __table_args__ = (
        CheckConstraint(
            "transaction_type IN ('TOPUP', 'CLASS_PAYMENT', 'TIP', 'CASHOUT', 'ADMIN_REWARD')",
            name="ck_point_transactions_type",
        ),
        Index("ix_point_transactions_user_created", "user_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    escrow_after: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    transaction_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    reference_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)


class CashoutRequest(Base, TimestampMixin):
    __tablename__ = "cashout_requests"
    __table_args__ = (
        CheckConstraint("points_amount >= 10", name="ck_cashout_requests_min_points"),
        CheckConstraint("status IN ('PENDING', 'APPROVED', 'REJECTED')", name="ck_cashout_requests_status"),
        CheckConstraint("net_amount_usd >= 0", name="ck_cashout_requests_net_positive"),
        Index("ix_cashout_requests_user_status", "user_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    points_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    gross_amount_usd: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    fee_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("15.00"), server_default="15.00")
    fee_amount_usd: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    net_amount_usd: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING", server_default="PENDING", index=True)
    bank_name: Mapped[str] = mapped_column(String(100), nullable=False)
    account_number: Mapped[str] = mapped_column(String(100), nullable=False)
    account_holder_name: Mapped[str] = mapped_column(String(150), nullable=False)
    account_holder_id: Mapped[str] = mapped_column(String(50), nullable=False)
    admin_notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
