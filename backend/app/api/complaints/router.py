"""Router API para quejas de miembros (HU-43 / RF-GOV-01)."""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.exceptions import SkillMatchException
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.complaint import ComplaintCreateRequest, ComplaintResponse
from app.schemas.response import APIResponse
from app.services.complaint_service import ComplaintService

router = APIRouter(prefix="/complaints", tags=["Centro de Quejas"])


async def current_member(user: User = Depends(get_current_user)) -> User:
    """Restringe el uso al rol MEMBER."""
    if user.role != UserRole.MEMBER:
        raise SkillMatchException("Recurso no encontrado", statuscode=404)
    return user


@router.post(
    "",
    response_model=APIResponse[ComplaintResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Radicar una queja formal",
    description="Permite al miembro reportar un inconveniente o disputa relacionada o no con una sesión formativa.",
)
async def submit_complaint(
    payload: ComplaintCreateRequest,
    user: User = Depends(current_member),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[ComplaintResponse]:
    data = await ComplaintService.create_complaint(db, user, payload)
    return APIResponse.created(
        data=data,
        message="Queja radicada exitosamente. El equipo de soporte y moderación la evaluará a la brevedad.",
    )


@router.get(
    "/my",
    response_model=APIResponse[List[ComplaintResponse]],
    summary="Consultar mis quejas radicadas",
    description="Devuelve el historial inmutable de quejas emitidas por el miembro autenticado con sus estados y respuestas oficiales.",
)
async def list_my_complaints(
    user: User = Depends(current_member),
    db: AsyncSession = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> APIResponse[List[ComplaintResponse]]:
    items, total = await ComplaintService.get_user_complaints(
        db, user_id=user.id, page=page, page_size=page_size
    )
    return APIResponse.ok(
        data=items,
        count=total,
        message="Historial de quejas consultado exitosamente.",
    )
