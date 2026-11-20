from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.session_review import SessionReviewResponse


class RatingsBreakdown(BaseModel):
    punctuality: float = Field(..., description="Promedio de puntualidad (1.00 a 5.00)")
    pedagogy: float = Field(..., description="Promedio de pedagogía (1.00 a 5.00)")
    domain: float = Field(..., description="Promedio de dominio técnico (1.00 a 5.00)")


class TrustScoreFactors(BaseModel):
    ia_verified_score: float = Field(..., description="Puntaje obtenido por validaciones superadas con IA (0 a 100)")
    peer_feedback_score: float = Field(..., description="Puntaje obtenido por feedback de la comunidad (0 a 100)")
    attendance_score: float = Field(..., description="Puntaje obtenido por asistencia y cumplimiento (0 a 100)")
    tenure_score: float = Field(..., description="Puntaje obtenido por antigüedad y fidelidad (0 a 100)")


class ReputationBadge(BaseModel):
    code: str = Field(..., description="Código de la insignia, ej: VERIFIED_IDENTITY")
    title: str = Field(..., description="Título visible de la medalla")
    description: str = Field(..., description="Explicación o tooltip de cómo se obtuvo")
    icon: str = Field(..., description="Nombre del icono de lucide-react")
    is_active: bool = Field(True, description="Si el usuario cumple las condiciones de la insignia")


class UserReputationResponse(BaseModel):
    user_id: UUID
    full_name: str
    avatar_url: Optional[str] = None
    trust_score: float = Field(..., description="Puntaje consolidado de confianza (0.00 a 100.00)")
    overall_rating: float = Field(..., description="Promedio general de estrellas recibidas (1.00 a 5.00)")
    total_reviews: int = Field(..., description="Total de reseñas recibidas")
    ratings_breakdown: RatingsBreakdown
    factors: TrustScoreFactors
    badges: List[ReputationBadge]
    recent_reviews: List[SessionReviewResponse]
