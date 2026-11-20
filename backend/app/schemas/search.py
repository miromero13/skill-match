from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field

from app.models.user import ExchangeModality


class TutorSearchFilterParams(BaseModel):
    """Parámetros para la búsqueda facetada y multidimensional de instructores (HU-20 / RF-MAT-01, RF-MAT-02, RF-MAT-11)."""
    query: Optional[str] = Field(default=None, description="Búsqueda por texto libre en nombre, bio o habilidad")
    skill_id: Optional[UUID] = Field(default=None, description="Filtrar por ID de habilidad específica")
    category_id: Optional[UUID] = Field(default=None, description="Filtrar por ID de categoría")
    min_level: Optional[str] = Field(default=None, description="Nivel mínimo declarado: BEGINNER, INTERMEDIATE, ADVANCED, EXPERT")
    verified_only: bool = Field(default=False, description="Filtrar exclusivamente instructores con habilidad verificada por IA")
    modality: Optional[ExchangeModality] = Field(default=None, description="Modalidad de enseñanza: VIRTUAL, PRESENCIAL, BOTH")
    max_distance: Optional[float] = Field(default=None, ge=0.0, description="Distancia máxima en kilómetros para clases presenciales")
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0, description="Latitud de referencia del aprendiz")
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0, description="Longitud de referencia del aprendiz")
    sort_by: Optional[str] = Field(
        default="reputation",
        description="Criterio de orden: reputation (reputación/compatibilidad), distance (cercanía), points_asc, points_desc, experience, recent",
    )
    page: int = Field(default=1, ge=1, description="Número de página (1-based)")
    page_size: int = Field(default=10, ge=1, le=100, description="Cantidad de resultados por página")


class TutorTeachingSkillItem(BaseModel):
    """Detalle de una habilidad ofrecida por el instructor dentro de los resultados."""
    id: UUID
    skill_id: UUID
    skill_name: str
    category_id: UUID
    category_name: str
    declared_level: str
    years_of_experience: int
    description: Optional[str] = None
    accepts_points: bool = False
    hourly_points_rate: Optional[int] = None
    status: str = "DECLARADA"
    is_verified: bool = False

    model_config = {"from_attributes": True}


class TutorSearchResultItem(BaseModel):
    """Perfil de instructor resultante de la búsqueda con datos enriquecidos y geodistancia."""
    id: UUID
    full_name: str
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    location_label: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    exchange_modality: ExchangeModality = ExchangeModality.VIRTUAL
    presencial_radius_km: int = 10
    distance_km: Optional[float] = None
    rating: float = 5.0
    total_reviews: int = 0
    has_verified_skills: bool = False
    skills: list[TutorTeachingSkillItem] = Field(default_factory=list)
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
