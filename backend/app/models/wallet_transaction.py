from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class WalletTransaction(Base, TimestampMixin):
    """
    Auditoría inmutable de movimientos de puntos (SkillPoints) entre billeteras de usuarios.
    Soporta propinas voluntarias (TIP), recargas y pagos de clases (HU-40 / HU-42).
    """
    __tablename__ = "wallet_transactions"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_wallet_transactions_positive_amount"),
        CheckConstraint(
            "type IN ('TIP', 'RECHARGE', 'CLASS_PAYMENT', 'REFUND', 'ADMIN_ADJUSTMENT')",
            name="ck_wallet_transactions_type",
        ),
        Index("ix_wallet_transactions_source_created", "source_user_id", "created_at"),
        Index("ix_wallet_transactions_target_created", "target_user_id", "created_at"),
        Index("ix_wallet_transactions_session", "session_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    target_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("exchange_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Cantidad de SkillPoints transferidos
    amount: Mapped[int] = mapped_column(Integer, nullable=False)

    # Tipo de transacción: 'TIP', 'RECHARGE', etc.
    type: Mapped[str] = mapped_column(String(30), nullable=False, default="TIP")

    # Nota o dedicatoria opcional (ej: "¡Excelente clase de Python!")
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
