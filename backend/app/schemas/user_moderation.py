from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field

from app.models.user_report import ReportReason, ReportStatus


class BlockUserRequest(BaseModel):
    """Payload opcional para bloquear a un usuario."""
    reason: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Motivo del bloqueo (ej. HARASSMENT, NO_SHOW, SPAM_FRAUD, OTHER)",
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Notas o justificación contextual del bloqueo",
    )


class BlockedUserItem(BaseModel):
    """Información de un usuario bloqueado para la vista /settings/privacy."""
    block_id: UUID
    user_id: UUID
    full_name: str
    avatar_url: Optional[str] = None
    reason: Optional[str] = None
    blocked_at: datetime


class ReportUserRequest(BaseModel):
    """Payload para enviar reporte formal a moderación administrativa (RF-NOT-06 / Vista 26/28)."""
    reason: ReportReason = Field(
        description="Tipología de la infracción seleccionada en el modal",
    )
    description: str = Field(
        min_length=10,
        max_length=1000,
        description="Detalle explicativo y pruebas de la infracción",
    )
    evidence_url: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Enlace opcional a captura o evidencia externa",
    )
    block_user: bool = Field(
        default=True,
        description="Si es True, aplica de inmediato el bloqueo preventivo automático (RF-MAT-14)",
    )


class ReportUserResponse(BaseModel):
    """Respuesta tras enviar un reporte a la moderación."""
    report_id: UUID
    reported_id: UUID
    reported_name: str
    reason: str
    status: str
    created_at: datetime
    user_blocked: bool


class UserSafetyStatusResponse(BaseModel):
    """Estado de seguridad y restricciones de interacción entre el usuario y otro miembro."""
    target_user_id: UUID
    is_blocked_by_me: bool
    is_blocking_me: bool
    can_interact: bool
    blocked_at: Optional[datetime] = None
