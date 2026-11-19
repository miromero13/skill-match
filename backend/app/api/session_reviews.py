from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.response import APIResponse
from app.schemas.session_review import (
    CreateSessionReviewRequest,
    SendSessionTipRequest,
    SessionReviewResponse,
    SessionReviewStateResponse,
    SessionTipResponse,
)
from app.services.reputation_service import ReputationService

router = APIRouter(
    prefix="/sessions",
    tags=["Session Reviews & Tipping (HU-40)"],
)


@router.get(
    "/{session_id}/review",
    response_model=APIResponse[SessionReviewStateResponse],
    status_code=status.HTTP_200_OK,
    summary="Consultar estado de calificación de la sesión (HU-40 / RF-REP-01)",
    description="Permite al miembro participante verificar si ya emitió su reseña y el estado de la contraparte.",
)
async def get_session_review_state(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> APIResponse[SessionReviewStateResponse]:
    state = await ReputationService.get_session_review_state(db, session_id, current_user)
    return APIResponse.ok(
        data=state,
        message="Estado de reseña consultado exitosamente.",
    )


@router.post(
    "/{session_id}/review",
    response_model=APIResponse[SessionReviewResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Emitir reseña pedagógica bilateral (HU-40 / RF-REP-01)",
    description="Registra la calificación en 3 criterios (puntualidad, pedagogía, dominio) y comentario moderado.",
)
async def submit_session_review(
    session_id: UUID,
    payload: CreateSessionReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> APIResponse[SessionReviewResponse]:
    review = await ReputationService.create_review(db, session_id, payload, current_user)
    return APIResponse(
        statuscode=status.HTTP_201_CREATED,
        message="¡Reseña publicada exitosamente! Gracias por contribuir a la confianza de la comunidad.",
        data=review,
    )


@router.post(
    "/{session_id}/tip",
    response_model=APIResponse[SessionTipResponse],
    status_code=status.HTTP_200_OK,
    summary="Enviar propina voluntaria en puntos (HU-40 / RF-REP-01)",
    description="Debita puntos de la billetera del alumno y los transfiere al tutor como agradecimiento.",
)
async def send_session_tip(
    session_id: UUID,
    payload: SendSessionTipRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> APIResponse[SessionTipResponse]:
    tip = await ReputationService.send_tip(db, session_id, payload, current_user)
    return APIResponse.ok(
        data=tip,
        message=f"¡Propina de {tip.amount} SkillPoints enviada con éxito a tu tutor!",
    )
