import uuid
from enum import Enum
from typing import Optional, TYPE_CHECKING
from sqlalchemy import Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.catalog import Skill


class UrgencyLevel(str, Enum):
    """Nivel de urgencia o prioridad para aprender una habilidad (HU-15 / RF-HAB-03)."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class UserLearningSkill(Base, TimestampMixin):
    """
    Entidad de persistencia para la demanda formativa del miembro (habilidades que desea aprender).
    Corresponde a HU-15 / RF-HAB-03.
    """
    __tablename__ = "user_learning_skills"
    __table_args__ = (
        UniqueConstraint("user_id", "skill_id", name="uq_user_learning_skills_user_skill"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skills.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    current_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Nivel inicial o de partida declarado por el aprendiz (1 al 5)"
    )
    target_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
        comment="Nivel meta u objetivo deseado (1 al 5, >= current_level)"
    )
    urgency: Mapped[UrgencyLevel] = mapped_column(
        String(20),
        nullable=False,
        default=UrgencyLevel.MEDIUM,
        comment="Nivel de urgencia: LOW, MEDIUM o HIGH"
    )
    notes: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        default=None,
        comment="Notas adicionales o motivación de aprendizaje"
    )

    # Relaciones
    user: Mapped["User"] = relationship(back_populates="learning_skills")
    skill: Mapped["Skill"] = relationship(lazy="joined")
