"""Esquemas Pydantic para el Centro de Quejas y Arbitraje (HU-43 / RF-GOV-01, 02, 03)."""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.complaint import ComplaintReason, ComplaintStatus


class ComplaintCreateRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=150, description="Título sintético de la queja")
    reason: ComplaintReason = Field(..., description="Categoría/motivo tipificado del inconveniente")
    description: str = Field(..., min_length=10, max_length=2500, description="Detalle cronológico de lo ocurrido")
    session_id: Optional[UUID] = Field(default=None, description="ID de la sesión de intercambio o clase vinculada (opcional)")
    evidence_urls: List[str] = Field(default_factory=list, description="Enlaces o referencias a pruebas documentales o capturas")


class ComplaintResolveRequest(BaseModel):
    status: ComplaintStatus = Field(..., description="Resolución definitiva: RESOLVED o DISMISSED")
    admin_response: str = Field(..., min_length=5, max_length=2500, description="Dictamen arbitral vinculante para el usuario")
    points_to_compensate: int = Field(default=0, ge=0, le=5000, description="SkillPoints acreditados como reparación/compensación")


class ComplaintUserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: str


class ComplaintSessionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    modality: str
    status: str
    points_required: Optional[int] = 0


class ComplaintResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    session_id: Optional[UUID] = None
    session_modality: Optional[str] = None
    reason: str
    title: str
    description: str
    evidence_urls: List[str] = Field(default_factory=list)
    status: str
    admin_response: Optional[str] = None
    points_compensated: int = 0
    resolved_by_id: Optional[UUID] = None
    resolved_by_name: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
