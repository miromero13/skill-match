from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.notification import NotificationFilters, NotificationResponse
from app.schemas.realtime_notification import WebSocketTicketResponse
from app.schemas.response import APIResponse
from app.services.notification_service import NotificationService
from app.services.realtime_notification_publisher import realtime_notification_publisher
from app.services.websocket_ticket_service import WebSocketTicketService

router = APIRouter(
    prefix="/notifications", tags=["Notificaciones personales"],
    responses={
        401: {"model": APIResponse[None], "description": "Autenticación requerida o token inválido"},
        403: {"model": APIResponse[None], "description": "Cuenta inactiva"},
        404: {"model": APIResponse[None], "description": "Notificación inexistente, ajena o eliminada"},
        423: {"model": APIResponse[None], "description": "Cuenta bloqueada"},
    },
)


@router.get(
    "/ws-token",
    response_model=APIResponse[WebSocketTicketResponse],
    response_model_exclude={"count"},
    responses={
        200: {"description": "Ticket temporal emitido para el handshake WebSocket"},
        401: {"model": APIResponse[None], "description": "Autenticación requerida o token inválido"},
        403: {"model": APIResponse[None], "description": "Cuenta inactiva"},
        423: {"model": APIResponse[None], "description": "Cuenta bloqueada"},
    },
)
async def create_websocket_ticket(
    user: User = Depends(get_current_user),
):
    """Genera un JWT temporal exclusivo para `/ws/notifications`.

    El access token nunca se coloca en la URL WebSocket. El cliente solicita un
    ticket nuevo por intento. El ticket no sirve para rutas REST ni constituye
    una garantía distribuida de un solo uso en la versión inicial.
    """
    data = WebSocketTicketResponse(
        ticket=WebSocketTicketService.issue(user_id=user.id, role=user.role),
        expires_in=settings.WS_TICKET_EXPIRE_SECONDS,
    )
    return APIResponse.ok(data=data, message="Ticket WebSocket generado exitosamente.")


@router.get("", response_model=APIResponse[list[NotificationResponse]])
async def list_notifications(
    filters: Annotated[NotificationFilters, Query()],
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Lista únicamente avisos propios no eliminados para MEMBER o ADMIN.

    Orden created_at DESC, id ASC. count es el total después de filtros y antes
    de paginar, incluso en páginas vacías. unread omitido incluye todos;
    true solo no leídos y false solo leídos. category filtra la categoría derivada.
    Para el badge global: unread=true, page_size=1 y sin category; usar count.
    No expone identidades de eventos/destinatarios ni avisos ajenos a ADMIN.
    """
    items, total = await NotificationService.list_owned(db, user.id, filters)
    return APIResponse.ok(data=items, count=total, message="Notificaciones recuperadas exitosamente.")


@router.patch("/read-all", response_model=APIResponse[None], response_model_exclude={"count"})
async def mark_all_notifications_read(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Marca todas las no leídas propias no borradas, sin filtro de categoría.

    Operación sin body e idempotente. Afecta las filas visibles al snapshot del
    UPDATE; un aviso confirmado después permanece no leído. No altera avisos de
    otras cuentas ni el timestamp de los que ya estaban leídos. Devuelve data null.
    """
    await NotificationService.mark_all_read(db, user.id)
    return APIResponse.ok(message="Notificaciones marcadas como leídas.")


@router.patch("/{id}/read", response_model=APIResponse[NotificationResponse], response_model_exclude={"count"})
async def mark_notification_read(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Marca una notificación propia como leída, sin body.

    Reintentos conservan el primer read_at. Una notificación ajena, inexistente o
    eliminada responde 404, también para ADMIN. No otorga acceso a su evento de dominio.
    """
    item = await NotificationService.mark_read(db, user.id, id)
    return APIResponse.ok(data=item, message="Notificación marcada como leída.")


@router.delete("/{id}", response_model=APIResponse[None], response_model_exclude={"count"})
async def delete_notification(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Elimina lógicamente un aviso propio de la bandeja y del contador.

    Conserva su identidad para deduplicación, sin borrar la transacción o auditoría
    de origen. No promete borrado físico. Repetición, ID ajeno o inexistente: 404.
    Devuelve 200 con data null y sin count.
    """
    await NotificationService.delete_owned(db, user.id, id)
    return APIResponse.ok(message="Notificación eliminada exitosamente.")


@router.post("/test-emit", response_model=APIResponse[NotificationResponse], response_model_exclude={"count"})
async def test_emit_notification(
    title: str = "¡Nueva propuesta de intercambio! 🤝",
    message: str = "Tienes una nueva propuesta de intercambio para aprender Python.",
    notification_type: str = "MATCH_RECEIVED",
    target_user_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Dispara una notificación durable y la publica en tiempo real vía WebSocket."""
    recipient_id = target_user_id or user.id
    item = await NotificationService.emit_in_app(
        db,
        user_id=recipient_id,
        event_id=uuid4(),
        notification_type=notification_type,
        title=title,
        message=message,
    )
    await db.commit()
    data = None
    if item:
        await realtime_notification_publisher.publish_committed(item.id)
        data = NotificationResponse.model_validate(item)
    return APIResponse.ok(data=data, message="Notificación emitida en tiempo real.")
