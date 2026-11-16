import uuid
from sqlalchemy import String, Boolean, Integer, ForeignKey, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base, TimestampMixin


class UserAvailability(Base, TimestampMixin):
    """
    Franja horaria de disponibilidad semanal del miembro.
    """
    __tablename__ = "user_availabilities"
    __table_args__ = (
        CheckConstraint("day_of_week >= 0 AND day_of_week <= 6", name="ck_user_availabilities_day_range"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    day_of_week: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Día de la semana: 0=Lunes .. 6=Domingo",
    )
    start_time: Mapped[str] = mapped_column(
        String(5),
        nullable=False,
        comment="Hora de inicio en formato HH:MM (bloques de 30 min)",
    )
    end_time: Mapped[str] = mapped_column(
        String(5),
        nullable=False,
        comment="Hora de fin en formato HH:MM (bloques de 30 min)",
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    modality: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="BOTH",
    )

    user = relationship("User", back_populates="availabilities")
