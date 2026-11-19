from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class SessionReview(Base, TimestampMixin):
    """
    Registro inmutable de evaluación cuantitativa y cualitativa entre pares
    al finalizar una sesión de intercambio (RF-REP-01 / HU-40).
    """
    __tablename__ = "session_reviews"
    __table_args__ = (
        UniqueConstraint("session_id", "reviewer_id", name="uq_session_reviews_session_reviewer"),
        CheckConstraint("reviewer_id <> reviewed_id", name="ck_session_reviews_distinct_members"),
        CheckConstraint("rating_punctuality BETWEEN 1 AND 5", name="ck_session_reviews_punctuality"),
        CheckConstraint("rating_pedagogy BETWEEN 1 AND 5", name="ck_session_reviews_pedagogy"),
        CheckConstraint("rating_domain BETWEEN 1 AND 5", name="ck_session_reviews_domain"),
        CheckConstraint("overall_rating >= 1.0 AND overall_rating <= 5.0", name="ck_session_reviews_overall"),
        CheckConstraint(
            "comment IS NULL OR (length(btrim(comment)) >= 10 AND length(btrim(comment)) <= 500)",
            name="ck_session_reviews_comment_length",
        ),
        CheckConstraint("role_in_session IN ('INSTRUCTOR', 'LEARNER')", name="ck_session_reviews_role"),
        Index("ix_session_reviews_reviewed_created", "reviewed_id", "created_at"),
        Index("ix_session_reviews_session", "session_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("exchange_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    reviewer_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    reviewed_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Rol del evaluado durante la sesión: 'INSTRUCTOR' o 'LEARNER'
    role_in_session: Mapped[str] = mapped_column(String(20), nullable=False)

    # Criterios pedagógicos cuantitativos (1 a 5 estrellas)
    rating_punctuality: Mapped[int] = mapped_column(Integer, nullable=False)
    rating_pedagogy: Mapped[int] = mapped_column(Integer, nullable=False)
    rating_domain: Mapped[int] = mapped_column(Integer, nullable=False)

    # Promedio consolidado de las 3 dimensiones (ej: 4.67)
    overall_rating: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False)

    # Feedback cualitativo opcional (10 a 500 caracteres sanitizados)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Visibilidad pública en el muro de reputación
    is_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
