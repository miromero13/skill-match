"""Admin diagnostics for native push (FCM): Firebase init state, device counts and test push.

Admin-only (`get_current_admin_user`): anonymous and MEMBER callers get the obfuscated 404.
Responses never include full FCM tokens or credential content.
"""
from collections import defaultdict
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_admin_user
from app.db.session import get_db
from app.models.device_push_token import DevicePushToken
from app.schemas.push_diagnostics import (
    FirebaseStatus,
    PushDeviceCounts,
    PushStatusResponse,
    PushTestRequest,
    PushTestResponse,
    PushTestResult,
)
from app.schemas.response import APIResponse
from app.services.fcm_service import FCMService, ensure_firebase_initialized, get_firebase_status

router = APIRouter(
    prefix="/admin/push",
    tags=["admin-push"],
    dependencies=[Depends(get_current_admin_user)],
)

DEFAULT_TEST_TITLE = "Prueba de notificación SkillMatch"
DEFAULT_TEST_BODY = "Si ves este mensaje, las notificaciones push funcionan en este dispositivo."
RECENT_DEVICES_LIMIT = 5


@router.get(
    "/status",
    response_model=APIResponse[PushStatusResponse],
    summary="Estado de Firebase y de los dispositivos FCM registrados",
)
async def get_push_status(db: AsyncSession = Depends(get_db)) -> APIResponse[PushStatusResponse]:
    ensure_firebase_initialized()  # attempts init when not yet initialized; never raises
    active = DevicePushToken.is_active.is_(True)
    total, active_count, users_with_active = (await db.execute(select(
        func.count(),
        func.count().filter(active),
        func.count(distinct(DevicePushToken.user_id)).filter(active),
    ).select_from(DevicePushToken))).one()
    return APIResponse.ok(
        data=PushStatusResponse(
            firebase=FirebaseStatus(**get_firebase_status()),
            devices=PushDeviceCounts(active=active_count, total=total, users_with_active=users_with_active),
        ),
        message="Estado de notificaciones push obtenido",
    )


@router.post(
    "/test",
    response_model=APIResponse[PushTestResponse],
    summary="Enviar un push de prueba a un usuario o a los dispositivos activos más recientes",
)
async def send_test_push(
    payload: PushTestRequest,
    db: AsyncSession = Depends(get_db),
) -> APIResponse[PushTestResponse]:
    statement = select(DevicePushToken.user_id, DevicePushToken.fcm_token).where(DevicePushToken.is_active.is_(True))
    if payload.user_id is not None:
        statement = statement.where(DevicePushToken.user_id == payload.user_id)
    else:
        statement = statement.order_by(
            DevicePushToken.updated_at.desc(), DevicePushToken.created_at.desc(),
        ).limit(RECENT_DEVICES_LIMIT)
    by_user: dict[UUID, list[str]] = defaultdict(list)
    for user_id, token in (await db.execute(statement)).all():
        by_user[user_id].append(token)

    results: list[PushTestResult] = []
    for user_id, tokens in by_user.items():
        sent = await FCMService.send_to_tokens(
            tokens,
            title=payload.title or DEFAULT_TEST_TITLE,
            body=payload.body or DEFAULT_TEST_BODY,
            data={"type": "ADMIN_TEST"},
        )
        results.extend(PushTestResult(user_id=user_id, **item) for item in sent)

    ok = sum(1 for r in results if r.ok)
    message = (
        "No hay dispositivos activos para enviar el push de prueba"
        if not results else f"Push de prueba enviado: {ok} correcto(s), {len(results) - ok} fallido(s)"
    )
    return APIResponse.ok(
        data=PushTestResponse(sent=ok, failed=len(results) - ok, results=results),
        message=message,
    )
