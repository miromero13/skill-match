import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, TYPE_CHECKING
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class ReportReason(str, Enum):
    """Tipología canónica de infracción según vista 26/28 del prototipo oficial y RF-NOT-06."""
    HARASSMENT = "HARASSMENT"  # Conducta, lenguaje ofensivo o acoso durante la interacción
    PAYMENT_OUTSIDE = "PAYMENT_OUTSIDE"  # Solicitud de dinero o pago por fuera de SkillMatch
    NO_SHOW = "NO_SHOW"  # Inasistencias reiteradas sin aviso previo (No-Shows)
    SPAM_FRAUD = "SPAM_FRAUD"  # Spam, fraude o suplantación de identidad
    OTHER = "OTHER"  # Otro motivo documentado en la descripción


class ReportStatus(str, Enum):
    """Estado de resolución del incidente en la cola de moderación administrativa."""
    PENDING = "PENDING"
    UNDER_REVIEW = "UNDER_REVIEW"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class UserReport(Base, TimestampMixin):
    """
    Entidad de persistencia para el reporte formal de incidentes a la moderación administrativa (RF-NOT-06 / HU-26).
    """
    __tablename__ = "user_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    reporter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID del miembro denunciante",
    )
    reported_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID del usuario reportado",
    )
    reason: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Tipología de infracción (ReportReason)",
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Detalle explicativo y circunstancias de la infracción",
    )
    evidence_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        default=None,
        comment="Enlace opcional a captura de pantalla o evidencia externa",
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=ReportStatus.PENDING.value,
        index=True,
        comment="Estado actual en la cola de auditoría/moderación",
    )
    admin_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        default=None,
        comment="Resolución o anotaciones de los moderadores administrativos",
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        comment="Fecha en que la moderación resolvió el reporte",
    )

    # Relaciones
    reporter: Mapped["User"] = relationship("User", foreign_keys=[reporter_id])
    reported: Mapped["User"] = relationship("User", foreign_keys=[reported_id])

    __table_args__ = (
        CheckConstraint("reporter_id != reported_id", name="ck_user_reports_no_self_report"),
    )
