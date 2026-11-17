import uuid
from typing import Optional, TYPE_CHECKING
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class UserBlock(Base, TimestampMixin):
    """
    Entidad de persistencia para el bloqueo preventivo bilateral entre miembros (RF-MAT-14 / HU-26).
    Al bloquear a un usuario, cesa todo contacto y se anulan automáticamente coincidencias y propuestas activas.
    """
    __tablename__ = "user_blocks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    blocker_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID del miembro que efectúa el bloqueo preventivo",
    )
    blocked_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID del usuario que ha sido bloqueado",
    )
    reason: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        default=None,
        comment="Motivo general del bloqueo (ej. HARASSMENT, NO_SHOW, SPAM_FRAUD)",
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        default=None,
        comment="Notas adicionales o contexto privado del bloqueo para auditoría",
    )

    # Relaciones
    blocker: Mapped["User"] = relationship("User", foreign_keys=[blocker_id])
    blocked: Mapped["User"] = relationship("User", foreign_keys=[blocked_id])

    __table_args__ = (
        UniqueConstraint("blocker_id", "blocked_id", name="uq_user_blocks_blocker_blocked"),
        CheckConstraint("blocker_id != blocked_id", name="ck_user_blocks_no_self_block"),
    )
