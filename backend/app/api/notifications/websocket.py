"""Authenticated, user-directed WebSocket channel for HU-24."""
import logging

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from jose import JWTError
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.realtime_notification import WebSocketClientMessage, WebSocketPongMessage
from app.services.notification_connection_manager import notification_connection_manager
from app.services.websocket_ticket_service import WebSocketTicketIdentity, WebSocketTicketService

logger = logging.getLogger("skillmatch.notifications.websocket")
router = APIRouter(tags=["Notificaciones en tiempo real"])
MAX_CLIENT_MESSAGE_BYTES = 1024


async def authenticate_websocket_ticket(
    ticket: str | None,
    db: AsyncSession,
) -> WebSocketTicketIdentity:
    identity = WebSocketTicketService.validate(ticket or "")
    user = await db.scalar(select(User).where(User.id == identity.user_id))
    if user is None:
        raise ValueError("Usuario WebSocket inexistente.")
    persisted_role = UserRole(user.role).value
    if (
        persisted_role != identity.role
        or not user.is_active
        or user.is_locked
    ):
        raise ValueError("Usuario WebSocket no elegible.")
    return identity


@router.websocket("/ws/notifications")
async def notification_websocket(
    websocket: WebSocket,
    ticket: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    try:
        identity = await authenticate_websocket_ticket(ticket, db)
    except (JWTError, TypeError, ValueError):
        logger.warning("Handshake WebSocket de notificaciones rechazado")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await notification_connection_manager.connect(identity.user_id, websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            if len(raw.encode("utf-8")) > MAX_CLIENT_MESSAGE_BYTES:
                await websocket.close(code=status.WS_1009_MESSAGE_TOO_BIG)
                return
            try:
                message = WebSocketClientMessage.model_validate_json(raw)
            except ValidationError:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
            if message.event == "ping":
                await websocket.send_json(WebSocketPongMessage().model_dump())
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("Fallo en canal WebSocket de notificaciones para usuario %s", identity.user_id)
    finally:
        await notification_connection_manager.disconnect(identity.user_id, websocket)
