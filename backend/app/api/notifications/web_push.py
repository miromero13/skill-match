"""Protected MEMBER endpoints for browser/PWA Web Push subscriptions."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user
from app.core.exceptions import SkillMatchException
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.response import APIResponse
from app.schemas.web_push import (
    WebPushPublicKeyResponse,
    WebPushSubscriptionCreate,
    WebPushSubscriptionResponse,
)
from app.services.web_push_subscription_service import WebPushSubscriptionService

router = APIRouter(
    prefix="/notifications/push",
    tags=["Web Push"],
    responses={
        401: {"model": APIResponse[None], "description": "Autenticación requerida"},
        404: {"model": APIResponse[None], "description": "Suscripción inexistente o ajena"},
        409: {"model": APIResponse[None], "description": "Endpoint registrado por otra cuenta"},
        423: {"model": APIResponse[None], "description": "Cuenta bloqueada"},
    },
)


def require_member(user: User) -> None:
    if user.role != UserRole.MEMBER:
        raise SkillMatchException("Recurso no encontrado", statuscode=404)


@router.get(
    "/public-key",
    response_model=APIResponse[WebPushPublicKeyResponse],
    response_model_exclude={"count"},
)
async def get_web_push_public_key(
    user: Annotated[User, Depends(get_current_user)],
) -> APIResponse[WebPushPublicKeyResponse]:
    require_member(user)
    if not settings.WEB_PUSH_ENABLED or not settings.VAPID_PUBLIC_KEY:
        raise SkillMatchException("Web Push no está configurado.", statuscode=503)
    return APIResponse.ok(
        data=WebPushPublicKeyResponse(public_key=settings.VAPID_PUBLIC_KEY),
        message="Clave pública Web Push recuperada exitosamente.",
    )


@router.post(
    "/subscriptions",
    response_model=APIResponse[WebPushSubscriptionResponse],
    response_model_exclude={"count"},
    status_code=status.HTTP_201_CREATED,
)
async def register_web_push_subscription(
    payload: WebPushSubscriptionCreate,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> APIResponse[WebPushSubscriptionResponse]:
    require_member(user)
    item, created = await WebPushSubscriptionService.register(
        db, user_id=user.id, payload=payload,
    )
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    if created:
        return APIResponse.created(data=item, message="Dispositivo registrado para Web Push.")
    return APIResponse.ok(data=item, message="Suscripción Web Push actualizada exitosamente.")


@router.delete(
    "/subscriptions/{subscription_id}",
    response_model=APIResponse[None],
    response_model_exclude={"count"},
)
async def revoke_web_push_subscription(
    subscription_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> APIResponse[None]:
    require_member(user)
    await WebPushSubscriptionService.revoke(
        db, user_id=user.id, subscription_id=subscription_id,
    )
    return APIResponse.ok(message="Suscripción Web Push revocada exitosamente.")
