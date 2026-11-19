"""Router API Administrativo para Resolución de Disputas y Compensaciones (HU-43 / RF-GOV-02, 03)."""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_admin_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.complaint import (
    ComplaintResolveRequest,
    ComplaintResponse,
)
from app.schemas.response import APIResponse
from app.services.complaint_service import ComplaintService

router = APIRouter(
    prefix="/admin/complaints",
    tags=["admin-complaints"],
    dependencies=[Depends(get_current_admin_user)],
)


@router.get(
    "",
    response_model=APIResponse[List[ComplaintResponse]],
    summary="Listar quejas de la plataforma para moderación y arbitraje",
    description="Devuelve el catálogo de quejas radicadas por miembros con filtros por estado (OPEN, RESOLVED, DISMISSED).",
)
async def list_admin_complaints(
    status_filter: Optional[str] = Query(default=None, description="Filtro opcional: OPEN | RESOLVED | DISMISSED | ALL"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[List[ComplaintResponse]]:
    items, total = await ComplaintService.get_admin_complaints(
        db, status_filter=status_filter, page=page, page_size=page_size
    )
    return APIResponse.ok(
        data=items,
        count=total,
        message="Quejas administrativas recuperadas exitosamente.",
    )


@router.get(
    "/{complaint_id}",
    response_model=APIResponse[ComplaintResponse],
    summary="Detalle exhaustivo de una queja para arbitraje",
    description="Devuelve la información de la denuncia, pruebas, partes intervinientes y resolución previa si existe.",
)
async def get_admin_complaint_detail(
    complaint_id: UUID,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[ComplaintResponse]:
    item = await ComplaintService.get_complaint_by_id(db, complaint_id)
    return APIResponse.ok(
        data=item,
        message="Detalle de queja recuperado exitosamente.",
    )


@router.patch(
    "/{complaint_id}/resolve",
    response_model=APIResponse[ComplaintResponse],
    summary="Emitir dictamen arbitral y aplicar compensación en SkillPoints",
    description="El administrador responde oficialmente, cambia el estado a RESOLVED o DISMISSED y opcionalmente acredita puntos de compensación inmediatos en la billetera del miembro.",
)
async def resolve_complaint_endpoint(
    complaint_id: UUID,
    payload: ComplaintResolveRequest,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[ComplaintResponse]:
    data = await ComplaintService.resolve_complaint(db, admin, complaint_id, payload)
    msg = (
        f"Queja resuelta exitosamente. Se acreditaron +{payload.points_to_compensate} SP como compensación al miembro."
        if payload.points_to_compensate > 0
        else "Dictamen arbitral emitido y queja actualizada exitosamente."
    )
    return APIResponse.ok(
        data=data,
        message=msg,
    )
