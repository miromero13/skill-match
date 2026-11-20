"""Protected MEMBER endpoints for native mobile push tokens (FCM)."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.exceptions import SkillMatchException
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.device_push_token import DevicePushTokenRegister, DevicePushTokenResponse
from app.schemas.response import APIResponse
from app.services.fcm_service import FCMService

router = APIRouter(
    prefix="/notifications/devices",
    tags=["Mobile Push"],
    responses={
        401: {"model": APIResponse[None], "description": "Autenticación requerida"},
        404: {"model": APIResponse[None], "description": "Recurso no encontrado"},
    },
)


def require_member(user: User) -> None:
    if user.role != UserRole.MEMBER:
        raise SkillMatchException("Recurso no encontrado", statuscode=404)


@router.post(
    "",
    response_model=APIResponse[DevicePushTokenResponse],
    response_model_exclude={"count"},
    status_code=status.HTTP_201_CREATED,
)
async def register_device_push_token(
    payload: DevicePushTokenRegister,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> APIResponse[DevicePushTokenResponse]:
    require_member(user)
    device = await FCMService.register_device(db, user_id=user.id, payload=payload)
    return APIResponse.created(
        data=device,
        message="Dispositivo móvil registrado exitosamente para notificaciones push.",
    )


@router.delete(
    "/{fcm_token}",
    response_model=APIResponse[None],
    response_model_exclude={"count"},
)
async def deactivate_device_push_token(
    fcm_token: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> APIResponse[None]:
    require_member(user)
    await FCMService.deactivate_device(db, user_id=user.id, fcm_token=fcm_token)
    return APIResponse.ok(
        message="Dispositivo móvil desregistrado exitosamente de notificaciones push.",
    )
