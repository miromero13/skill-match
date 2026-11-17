from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field


class FactorBreakdown(BaseModel):
    """Desglose de cada factor ponderado de compatibilidad (HU-22 / RF-MAT-04, RF-MAT-06)."""
    score: int = Field(ge=0, le=100, description="Puntaje bruto del factor de 0 a 100")
    weight: int = Field(description="Ponderación porcentual del factor en la matriz (ej. 40, 25, 20, 15)")
    weighted_score: float = Field(description="Puntaje ponderado aportado al score final")
    description: str = Field(description="Explicación descriptiva del factor")


class CompatibilityFactors(BaseModel):
    """Factores de la matriz ponderada de compatibilidad."""
    skill_affinity: FactorBreakdown = Field(description="Afinidad de habilidades ofrecidas y deseadas (40%)")
    schedule_overlap: FactorBreakdown = Field(description="Coincidencia de disponibilidad horaria semanal (25%)")
    modality_location: FactorBreakdown = Field(description="Compatibilidad de modalidad y cercanía geográfica (20%)")
    reputation_verification: FactorBreakdown = Field(description="Sello de verificación por IA y reputación previa (15%)")


class MatchCompatibilityResponse(BaseModel):
    """Respuesta con el score porcentual y la explicabilidad determinística del match."""
    match_id: Optional[UUID] = None
    counterpart_id: UUID
    counterpart_name: str
    compatibility_score: int = Field(ge=0, le=100, description="Score global de compatibilidad de 0 a 100%")
    factors: CompatibilityFactors
    match_reasons: list[str] = Field(default_factory=list, description="Lista de razones legibles que justifican la compatibilidad")


class MatchResponse(BaseModel):
    id: UUID
    counterpart_name: str
    counterpart_avatar_url: str | None = None
    member_name: str | None = None
    member_avatar_url: str | None = None
    you_verified: list[str] = []
    they_verified: list[str] = []
    status: str
    you_teach: list[str]
    they_teach: list[str]
    compatibility_score: Optional[int] = Field(default=None, description="Score porcentual de compatibilidad precalculado")
