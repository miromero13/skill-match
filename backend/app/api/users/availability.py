from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.response import APIResponse
from app.schemas.user_availability import (
    AvailabilityMatrixUpdate,
    AvailabilitySlotResponse,
)
from app.services.user_availability_service import UserAvailabilityService

router = APIRouter(
    prefix="/users/me/availability",
    tags=["Disponibilidad Semanal"],
)


@router.get(
    "",
    response_model=APIResponse[list[AvailabilitySlotResponse]],
)
async def get_my_availability(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items, count = await UserAvailabilityService.list_slots(db, current_user.id)
    return APIResponse.ok(
        data=items,
        count=count,
        message="Matriz de disponibilidad semanal recuperada exitosamente.",
    )


@router.put(
    "",
    response_model=APIResponse[list[AvailabilitySlotResponse]],
)
async def replace_my_availability(
    payload: AvailabilityMatrixUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items, count = await UserAvailabilityService.replace_matrix(db, current_user, payload)
    return APIResponse.ok(
        data=items,
        count=count,
        message="Matriz de disponibilidad semanal actualizada exitosamente.",
    )


@router.delete(
    "/{slot_id}",
    response_model=APIResponse[None],
    response_model_exclude={"count"},
)
async def delete_my_availability_slot(
    slot_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await UserAvailabilityService.delete_slot(db, current_user.id, slot_id)
    return APIResponse.ok(
        data=None,
        message="Franja horaria eliminada exitosamente.",
    )
