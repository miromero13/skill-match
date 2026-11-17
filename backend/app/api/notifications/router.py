from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.notification import NotificationFilters, NotificationResponse
from app.schemas.response import APIResponse
from app.services.notification_service import NotificationService

router = APIRouter(
    prefix="/notifications", tags=["Notificaciones personales"],
    responses={
        401: {"model": APIResponse[None], "description": "Autenticación requerida o token inválido"},
        403: {"model": APIResponse[None], "description": "Cuenta inactiva"},
        404: {"model": APIResponse[None], "description": "Notificación inexistente, ajena o eliminada"},
        423: {"model": APIResponse[None], "description": "Cuenta bloqueada"},
    },
)


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
