"""Modelo de Quejas y Arbitraje de Disputas (HU-43 / RF-GOV-01, RF-GOV-02, RF-GOV-03)."""
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.exchange_session import ExchangeSession
    from app.models.user import User


class ComplaintStatus(str, Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class ComplaintReason(str, Enum):
    NO_SHOW = "NO_SHOW"
    INAPPROPRIATE_BEHAVIOR = "INAPPROPRIATE_BEHAVIOR"
    TECHNICAL_FAILURE = "TECHNICAL_FAILURE"
    QUALITY_ISSUE = "QUALITY_ISSUE"
    PAYMENT_DISPUTE = "PAYMENT_DISPUTE"
    OTHER = "OTHER"


class Complaint(Base, TimestampMixin):
    __tablename__ = "complaints"
    __table_args__ = (
        CheckConstraint("points_compensated >= 0", name="ck_complaint_nonnegative_compensation"),
        Index("ix_complaints_user_status", "user_id", "status"),
        Index("ix_complaints_status_created", "status", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("exchange_sessions.id", ondelete="SET NULL"), nullable=True, index=True)

    reason: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_urls: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")

    status: Mapped[str] = mapped_column(String(20), default=ComplaintStatus.OPEN.value, server_default=ComplaintStatus.OPEN.value, nullable=False, index=True)

    admin_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    points_compensated: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    resolved_by_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relaciones
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], lazy="selectin")
    session: Mapped[Optional["ExchangeSession"]] = relationship("ExchangeSession", foreign_keys=[session_id], lazy="selectin")
    resolved_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[resolved_by_id], lazy="selectin")
