from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.reputation import UserReputationResponse
from app.schemas.response import APIResponse
from app.services.reputation_service import ReputationService

router = APIRouter(
    prefix="/users",
    tags=["User Reputation & Trust Score (HU-40 / RF-REP-02)"],
)


@router.get(
    "/{user_id}/reputation",
    response_model=APIResponse[UserReputationResponse],
    status_code=status.HTTP_200_OK,
    summary="Consultar reputación y Puntaje de Confianza de un miembro (HU-40 / RF-REP-02)",
    description="Retorna el Puntaje de Confianza (Trust Score 0-100), desglose de estrellas, insignias y testimonios.",
)
async def get_user_reputation(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> APIResponse[UserReputationResponse]:
    reputation = await ReputationService.get_user_reputation(db, user_id)
    return APIResponse.ok(
        data=reputation,
        message="Reputación y Puntaje de Confianza obtenidos exitosamente.",
    )
