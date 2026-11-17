from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.exceptions import SkillMatchException
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.response import APIResponse
from app.schemas.user_moderation import (
    BlockedUserItem,
    BlockUserRequest,
    ReportUserRequest,
    ReportUserResponse,
    UserSafetyStatusResponse,
)
from app.services.user_moderation_service import UserModerationService

router = APIRouter(
    prefix="/users",
    tags=["Usuarios · Bloqueo y Moderación (HU-26)"],
)


async def current_member(user: User = Depends(get_current_user)) -> User:
    """Verifica autenticación y acceso exclusivo para miembros."""
    if user.role != UserRole.MEMBER:
        raise SkillMatchException("Recurso no encontrado", statuscode=404)
    return user


@router.get(
    "/blocked",
    response_model=APIResponse[list[BlockedUserItem]],
    summary="Listado de usuarios bloqueados preventivamente (RF-MAT-14)",
    description="Retorna la lista de miembros bloqueados por el usuario autenticado con contador total.",
)
async def list_blocked_users(
    current_user: User = Depends(current_member),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[list[BlockedUserItem]]:
    items, count = await UserModerationService.list_blocked_users(db, current_user.id)
    return APIResponse.ok(
        data=items,
        count=count,
        message=(
            f"Se encontraron {count} usuario(s) bloqueado(s)."
            if count > 0
            else "No tienes usuarios bloqueados actualmente."
        ),
    )


@router.post(
    "/{id}/block",
    response_model=APIResponse[BlockedUserItem],
    response_model_exclude={"count"},
    summary="Bloqueo preventivo de usuario y anulación de trueques (RF-MAT-14)",
    description="Bloquea al usuario indicado y cancela de inmediato matches y propuestas pendientes.",
)
async def block_user(
    id: UUID,
    payload: BlockUserRequest = BlockUserRequest(),
    current_user: User = Depends(current_member),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[BlockedUserItem]:
    blocked_item = await UserModerationService.block_user(
        db,
        blocker_id=current_user.id,
        target_id=id,
        reason=payload.reason,
        notes=payload.notes,
    )
    return APIResponse.ok(
        data=blocked_item,
        message=f"Has bloqueado a {blocked_item.full_name}. Se han anulado todas las coincidencias y propuestas activas.",
    )


@router.delete(
    "/{id}/unblock",
    response_model=APIResponse[None],
    response_model_exclude={"count"},
    summary="Desbloquear a un usuario previamente bloqueado",
    description="Remueve la restricción de bloqueo permitiendo nuevamente coincidencias en el sistema.",
)
async def unblock_user(
    id: UUID,
    current_user: User = Depends(current_member),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[None]:
    await UserModerationService.unblock_user(db, blocker_id=current_user.id, target_id=id)
    return APIResponse.ok(
        data=None,
        message="Usuario desbloqueado exitosamente.",
    )


@router.post(
    "/{id}/report",
    response_model=APIResponse[ReportUserResponse],
    response_model_exclude={"count"},
    status_code=status.HTTP_201_CREATED,
    summary="Reporte formal de usuario a la cola de moderación (RF-NOT-06)",
    description="Envía un reporte formal a los moderadores con tipología de infracción y justificación.",
)
async def report_user(
    id: UUID,
    payload: ReportUserRequest,
    current_user: User = Depends(current_member),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[ReportUserResponse]:
    report_res = await UserModerationService.report_user(
        db,
        reporter_id=current_user.id,
        target_id=id,
        payload=payload,
    )
    return APIResponse(
        statuscode=status.HTTP_201_CREATED,
        message=(
            f"Reporte contra {report_res.reported_name} enviado a moderación administrativa exitosamente. "
            + ("El usuario fue bloqueado preventivamente." if report_res.user_blocked else "")
        ),
        data=report_res,
    )


@router.get(
    "/{id}/safety-status",
    response_model=APIResponse[UserSafetyStatusResponse],
    response_model_exclude={"count"},
    summary="Consulta estado de bloqueo y restricciones con otro miembro",
)
async def get_user_safety_status(
    id: UUID,
    current_user: User = Depends(current_member),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[UserSafetyStatusResponse]:
    status_res = await UserModerationService.get_safety_status(
        db, user_a_id=current_user.id, user_b_id=id
    )
    return APIResponse.ok(
        data=status_res,
        message="Estado de seguridad consultado.",
    )
