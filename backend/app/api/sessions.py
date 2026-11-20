from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.exceptions import SkillMatchException
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.exchange_session import (
    ExchangeSessionCancel,
    ExchangeSessionCreate,
    ExchangeSessionListResponse,
    ExchangeSessionReschedule,
    ExchangeSessionResponse,
    ExchangeSessionStatusUpdate,
    SessionCalendarExportResponse,
    SessionConfirmRequest,
    SessionConfirmResponse,
    SessionNoShowRequest,
    SessionNoShowResponse,
    SessionPresencePinResponse,
)
from app.schemas.response import APIResponse
from app.schemas.wallet import SessionPayResult
from app.services import exchange_session_service, session_completion_service
from app.services.wallet_service import wallet_service

router = APIRouter(prefix="/sessions", tags=["Sesiones de intercambio · HU-38"])


async def current_member(user: Annotated[User, Depends(get_current_user)]) -> User:
    """Restringe HU-38 a MEMBER y oculta el recurso a otros roles."""
    if user.role != UserRole.MEMBER:
        raise SkillMatchException("Recurso no encontrado", statuscode=404)
    return user


MemberDep = Annotated[User, Depends(current_member)]
DatabaseDep = Annotated[AsyncSession, Depends(get_db)]


@router.get(
    "",
    response_model=APIResponse[ExchangeSessionListResponse],
    summary="Listar mis sesiones",
    description="Devuelve exclusivamente las sesiones del miembro y su cupo gratuito semanal.",
)
async def list_sessions(
    user: MemberDep,
    db: DatabaseDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> APIResponse[ExchangeSessionListResponse]:
    items, total, remaining = await exchange_session_service.list_for_member(
        db,
        user,
        page,
        page_size,
    )
    return APIResponse.ok(
        data=ExchangeSessionListResponse(items=items, free_sessions_left=remaining),
        count=total,
        message="Sesiones recuperadas correctamente.",
    )


@router.get(
    "/{session_id}/calendar-export",
    response_model=APIResponse[SessionCalendarExportResponse],
    response_model_exclude={"count"},
    summary="Exportar sesión aceptada al calendario",
    description=(
        "Devuelve un archivo iCalendar y un enlace manual a Google Calendar. "
        "No solicita OAuth de Calendar ni realiza sincronización automática."
    ),
)
async def export_session_calendar(
    session_id: UUID,
    user: MemberDep,
    db: DatabaseDep,
) -> APIResponse[SessionCalendarExportResponse]:
    item = await exchange_session_service.get_calendar_export(db, user.id, session_id)
    return APIResponse.ok(data=item, message="Exportación de calendario generada correctamente.")


@router.post(
    "",
    response_model=APIResponse[ExchangeSessionResponse],
    response_model_exclude={"count"},
    status_code=status.HTTP_201_CREATED,
    summary="Proponer una sesión",
    description=(
        "Requiere un match confirmado y disponibilidad común. Con payment_method=FREE "
        "consume uno de los dos cupos semanales del aprendiz; con payment_method=POINTS "
        "reserva en escrow la tarifa configurada por el instructor mediante HU-42."
    ),
)
async def create_session(
    payload: ExchangeSessionCreate,
    user: MemberDep,
    db: DatabaseDep,
) -> APIResponse[ExchangeSessionResponse]:
    item = await exchange_session_service.create(db, user.id, payload)
    return APIResponse.created(data=item, message="Propuesta de sesión creada correctamente.")


@router.patch(
    "/{session_id}/status",
    response_model=APIResponse[ExchangeSessionResponse],
    response_model_exclude={"count"},
    summary="Aceptar o rechazar una propuesta",
    description="Solo la contraparte del proponente puede resolver una sesión pendiente.",
)
async def update_session_status(
    session_id: UUID,
    payload: ExchangeSessionStatusUpdate,
    user: MemberDep,
    db: DatabaseDep,
) -> APIResponse[ExchangeSessionResponse]:
    item = await exchange_session_service.update_status(db, user.id, session_id, payload.status)
    return APIResponse.ok(data=item, message="Estado de la sesión actualizado correctamente.")


@router.put(
    "/{session_id}/reschedule",
    response_model=APIResponse[ExchangeSessionResponse],
    response_model_exclude={"count"},
    summary="Reprogramar una sesión",
    description="Cualquiera de los participantes puede proponer el cambio; vuelve a PENDING.",
)
async def reschedule_session(
    session_id: UUID,
    payload: ExchangeSessionReschedule,
    user: MemberDep,
    db: DatabaseDep,
) -> APIResponse[ExchangeSessionResponse]:
    item = await exchange_session_service.reschedule(db, user.id, session_id, payload)
    return APIResponse.ok(data=item, message="Sesión reprogramada correctamente.")


@router.post(
    "/{session_id}/cancel",
    response_model=APIResponse[ExchangeSessionResponse],
    response_model_exclude={"count"},
    summary="Cancelar una sesión",
    description=(
        "Exige un motivo de 10 a 500 caracteres. Una cancelación con al menos 24 horas "
        "restaura el cupo; una tardía bloquea solo nuevas reservas durante siete días."
    ),
)
async def cancel_session(
    session_id: UUID,
    payload: ExchangeSessionCancel,
    user: MemberDep,
    db: DatabaseDep,
) -> APIResponse[ExchangeSessionResponse]:
    item = await exchange_session_service.cancel(
        db,
        user,
        session_id,
        payload.cancellation_reason,
    )
    return APIResponse.ok(data=item, message="Sesión cancelada correctamente.")


@router.post(
    "/{session_id}/confirm",
    response_model=APIResponse[SessionConfirmResponse],
    response_model_exclude={"count"},
    summary="Confirmar realización y horas de sesión",
    description=(
        "Protocolo de confirmación dual post-sesión. La primera confirmación registra las horas y temas; "
        "la segunda con horas concordantes completa la sesión a COMPLETED."
    ),
)
async def confirm_session(
    session_id: UUID,
    payload: SessionConfirmRequest,
    user: MemberDep,
    db: DatabaseDep,
) -> APIResponse[SessionConfirmResponse]:
    result = await session_completion_service.confirm_session(db, user, session_id, payload)
    message = (
        "Sesión completada exitosamente."
        if result.status == "COMPLETED"
        else "Confirmación de sesión registrada correctamente."
    )
    return APIResponse.ok(data=result, message=message)


@router.post(
    "/{session_id}/report-noshow",
    response_model=APIResponse[SessionNoShowResponse],
    response_model_exclude={"count"},
    summary="Reportar inasistencia (no-show)",
    description=(
        "Permite a un participante registrar la inasistencia injustificada de la contraparte "
        "después de concluida la sesión."
    ),
)
async def report_noshow(
    session_id: UUID,
    payload: SessionNoShowRequest,
    user: MemberDep,
    db: DatabaseDep,
) -> APIResponse[SessionNoShowResponse]:
    result = await session_completion_service.report_noshow(db, user, session_id, payload)
    return APIResponse.ok(
        data=result,
        message="Reporte de inasistencia registrado correctamente.",
    )


@router.get(
    "/{session_id}/presence-pin",
    response_model=APIResponse[SessionPresencePinResponse],
    response_model_exclude={"count"},
    summary="Consultar o generar PIN presencial",
    description="Devuelve el PIN de 4 dígitos para validación mutua en sesiones presenciales.",
)
async def get_presence_pin(
    session_id: UUID,
    user: MemberDep,
    db: DatabaseDep,
) -> APIResponse[SessionPresencePinResponse]:
    result = await session_completion_service.get_or_create_presence_pin(db, user, session_id)
    return APIResponse.ok(
        data=result,
        message="PIN de presencia obtenido correctamente.",
    )


@router.post(
    "/{session_id}/pay",
    response_model=APIResponse[SessionPayResult],
    response_model_exclude={"count"},
    summary="Asegurar clase no recíproca con puntos Escrow (HU-42)",
    description="Bloquea los puntos requeridos en custodia Escrow hasta la conclusión y confirmación de la sesión.",
)
async def pay_session(
    session_id: UUID,
    user: MemberDep,
    db: DatabaseDep,
) -> APIResponse[SessionPayResult]:
    result = await wallet_service.pay_session_escrow(db, user.id, session_id)
    return APIResponse.ok(
        data=result,
        message=result.message,
    )
