from uuid import UUID
from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import SkillMatchException
from app.models.user import User
from app.models.user_availability import UserAvailability
from app.schemas.user_availability import (
    AvailabilityMatrixUpdate,
    AvailabilitySlotResponse,
)


class UserAvailabilityService:
    """Servicio de dominio para gestionar la matriz de disponibilidad semanal."""

    @staticmethod
    async def list_slots(
        db: AsyncSession,
        user_id: UUID,
    ) -> tuple[list[AvailabilitySlotResponse], int]:
        result = await db.execute(
            select(UserAvailability).where(UserAvailability.user_id == user_id)
        )
        items = list(result.scalars().all())
        items.sort(key=lambda s: (s.day_of_week, s.start_time))
        responses = [AvailabilitySlotResponse.model_validate(item) for item in items]
        return responses, len(responses)

    @classmethod
    async def replace_matrix(
        cls,
        db: AsyncSession,
        user: User,
        payload: AvailabilityMatrixUpdate,
    ) -> tuple[list[AvailabilitySlotResponse], int]:
        # Si se envían preferencias de agenda (timezone o buffer_minutes), sincronizarlas directo en User
        if payload.timezone is not None:
            user.timezone = payload.timezone
        if payload.buffer_minutes is not None:
            user.buffer_minutes = payload.buffer_minutes

        # Eliminar franjas anteriores del miembro
        existing_result = await db.execute(
            select(UserAvailability).where(UserAvailability.user_id == user.id)
        )
        existing_slots = list(existing_result.scalars().all())
        for old_slot in existing_slots:
            await db.delete(old_slot)

        # Insertar nueva matriz semanal
        new_entities: list[UserAvailability] = []
        for slot_in in payload.slots:
            entity = UserAvailability(
                user_id=user.id,
                day_of_week=slot_in.day_of_week,
                start_time=slot_in.start_time,
                end_time=slot_in.end_time,
                is_enabled=slot_in.is_enabled,
                modality=slot_in.modality,
            )
            db.add(entity)
            new_entities.append(entity)

        await db.commit()
        for entity in new_entities:
            await db.refresh(entity)

        new_entities.sort(key=lambda s: (s.day_of_week, s.start_time))
        responses = [AvailabilitySlotResponse.model_validate(item) for item in new_entities]
        return responses, len(responses)

    @staticmethod
    async def delete_slot(
        db: AsyncSession,
        user_id: UUID,
        slot_id: UUID,
    ) -> None:
        result = await db.execute(
            select(UserAvailability).where(
                UserAvailability.id == slot_id,
                UserAvailability.user_id == user_id,
            )
        )
        slot = result.scalar_one_or_none()
        if slot is None:
            raise SkillMatchException(
                statuscode=status.HTTP_404_NOT_FOUND,
                message="La franja horaria solicitada no existe o no pertenece a tu perfil.",
            )
        await db.delete(slot)
        await db.commit()
