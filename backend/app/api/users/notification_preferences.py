from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.notification import NotificationPreferencesResponse, NotificationPreferencesWrite
from app.schemas.response import APIResponse
from app.services.notification_service import NotificationService

router = APIRouter(
    prefix="/users/me/notification-preferences", tags=["Preferencias de notificaciones"],
    responses={
        401: {"model": APIResponse[None], "description": "Autenticación requerida o token inválido"},
        403: {"model": APIResponse[None], "description": "Cuenta inactiva"},
        404: {"model": APIResponse[None], "description": "Destinatario no disponible"},
        423: {"model": APIResponse[None], "description": "Cuenta bloqueada"},
    },
)


@router.get("", response_model=APIResponse[NotificationPreferencesResponse], response_model_exclude={"count"})
async def get_notification_preferences(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Recupera preferencias propias efectivas para MEMBER y ADMIN.

    Sin fila devuelve revision 0 sin insertar: in_app true; push/email false;
    categorías INTERCHANGES/POINTS/GENERAL true. No habilita permisos del dispositivo
    ni proveedores de entrega. ADMIN no puede consultar preferencias de otra cuenta.
    """
    preferences = await NotificationService.get_preferences(db, user.id)
    return APIResponse.ok(data=preferences, message="Preferencias de notificaciones recuperadas exitosamente.")


@router.put(
    "", response_model=APIResponse[NotificationPreferencesResponse], response_model_exclude={"count"},
    responses={409: {"model": APIResponse[None], "description": "Revisión obsoleta; recargar y reconciliar antes de guardar"}},
)
async def update_notification_preferences(
    payload: NotificationPreferencesWrite,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Reemplaza todas las preferencias propias usando la revisión esperada.

    Todos los flags de channels/categories son obligatorios y estrictamente booleanos;
    no acepta user_id, timestamps ni campos extra. Primer guardado con revision 0
    materializa revision 1; siguientes incrementan una revisión. Si otra solicitud
    ganó, devuelve 409 sin sobrescribir. Cambios afectan emisión futura, no el histórico.
    push/email expresan preferencias: este endpoint no envía mensajes externos.
    """
    preferences = await NotificationService.update_preferences(db, user.id, payload)
    return APIResponse.ok(data=preferences, message="Preferencias de notificaciones actualizadas exitosamente.")
