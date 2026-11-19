from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CreateSessionReviewRequest(BaseModel):
    rating_punctuality: int = Field(
        ..., ge=1, le=5, description="Calificación de puntualidad y asistencia (1 a 5 estrellas)"
    )
    rating_pedagogy: int = Field(
        ..., ge=1, le=5, description="Calificación de pedagogía y claridad metodológica (1 a 5 estrellas)"
    )
    rating_domain: int = Field(
        ..., ge=1, le=5, description="Calificación de dominio técnico de la habilidad (1 a 5 estrellas)"
    )
    comment: Optional[str] = Field(
        None,
        min_length=10,
        max_length=500,
        description="Comentario y testimonio de la clase (opcional, entre 10 y 500 caracteres)",
    )


class SessionReviewResponse(BaseModel):
    id: UUID
    session_id: UUID
    reviewer_id: UUID
    reviewer_name: str
    reviewer_avatar: Optional[str] = None
    reviewed_id: UUID
    role_in_session: str
    rating_punctuality: int
    rating_pedagogy: int
    rating_domain: int
    overall_rating: float
    comment: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class SendSessionTipRequest(BaseModel):
    amount: int = Field(
        ...,
        gt=0,
        le=500,
        description="Cantidad voluntaria de SkillPoints a donar (ej. 5, 10, 25 SP)",
    )
    note: Optional[str] = Field(
        None,
        max_length=140,
        description="Mensaje corto de agradecimiento al tutor",
    )


class SessionTipResponse(BaseModel):
    transaction_id: UUID
    amount: int
    new_balance: int
    target_user_id: UUID
    note: Optional[str] = None
    created_at: datetime


class SessionReviewStateResponse(BaseModel):
    session_id: UUID
    can_review: bool
    has_reviewed: bool
    reviewed_by_counterpart: bool
    existing_review: Optional[SessionReviewResponse] = None
