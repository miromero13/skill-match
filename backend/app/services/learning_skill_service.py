import logging
import uuid
from typing import List, Optional
from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import SkillMatchException
from app.models.catalog import Skill
from app.models.user_learning_skill import UserLearningSkill
from app.schemas.user_learning_skill import (
    UserLearningSkillCreate,
    UserLearningSkillUpdate,
    UserLearningSkillResponse,
    SkillSummary,
)

logger = logging.getLogger("skillmatch.services.learning_skills")


class LearningSkillService:
    """
    Servicio de dominio para la gestión de demandas formativas de miembros (HU-15 / RF-HAB-03).
    Permite a los usuarios registrar, consultar, actualizar y eliminar habilidades que desean aprender.
    """

    @staticmethod
    def _map_to_response(item: UserLearningSkill) -> UserLearningSkillResponse:
        skill_summary: Optional[SkillSummary] = None
        if item.skill:
            category_name = item.skill.category.name if item.skill.category else None
            skill_summary = SkillSummary(
                id=item.skill.id,
                name=item.skill.name,
                slug=item.skill.slug,
                category_id=item.skill.category_id,
                category_name=category_name,
            )

        return UserLearningSkillResponse(
            id=item.id,
            user_id=item.user_id,
            skill_id=item.skill_id,
            current_level=item.current_level,
            target_level=item.target_level,
            urgency=item.urgency,
            notes=item.notes,
            skill=skill_summary,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )

    @classmethod
    async def list_user_learning_skills(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> List[UserLearningSkillResponse]:
        """Obtiene todas las habilidades que el miembro desea aprender con relaciones cargadas."""
        query = (
            select(UserLearningSkill)
            .where(UserLearningSkill.user_id == user_id)
            .options(
                selectinload(UserLearningSkill.skill).selectinload(Skill.category)
            )
            .order_by(UserLearningSkill.created_at.desc())
        )
        result = await db.execute(query)
        items = result.scalars().all()
        return [cls._map_to_response(item) for item in items]

    @classmethod
    async def add_learning_skill(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        payload: UserLearningSkillCreate,
    ) -> UserLearningSkillResponse:
        """Registra una nueva habilidad que el miembro desea aprender."""
        # 1. Validar que la habilidad exista en el catálogo y esté activa
        skill_query = (
            select(Skill)
            .options(selectinload(Skill.category))
            .where(Skill.id == payload.skill_id)
        )
        skill_result = await db.execute(skill_query)
        skill = skill_result.scalar_one_or_none()

        if not skill:
            raise SkillMatchException(
                statuscode=status.HTTP_404_NOT_FOUND,
                message="La habilidad seleccionada no existe en el catálogo maestro.",
            )

        # 2. Verificar que el miembro no la tenga registrada previamente (Restricción de unicidad)
        existing_query = select(UserLearningSkill).where(
            UserLearningSkill.user_id == user_id,
            UserLearningSkill.skill_id == payload.skill_id,
        )
        existing_result = await db.execute(existing_query)
        if existing_result.scalar_one_or_none():
            raise SkillMatchException(
                statuscode=status.HTTP_409_CONFLICT,
                message=f"Ya tienes '{skill.name}' registrada en tu lista de habilidades por aprender.",
            )

        # 3. Validar consistencia de niveles
        if payload.target_level < payload.current_level:
            raise SkillMatchException(
                statuscode=status.HTTP_422_UNPROCESSABLE_ENTITY,
                message="El nivel meta (target_level) debe ser mayor o igual al nivel actual (current_level).",
            )

        # 4. Crear entidad
        learning_skill = UserLearningSkill(
            user_id=user_id,
            skill_id=payload.skill_id,
            current_level=payload.current_level,
            target_level=payload.target_level,
            urgency=payload.urgency,
            notes=payload.notes,
        )
        db.add(learning_skill)
        await db.commit()

        # Recargar con relaciones
        reloaded_query = (
            select(UserLearningSkill)
            .where(UserLearningSkill.id == learning_skill.id)
            .options(
                selectinload(UserLearningSkill.skill).selectinload(Skill.category)
            )
        )
        reloaded_result = await db.execute(reloaded_query)
        saved = reloaded_result.scalar_one()

        logger.info(f"Usuario {user_id} registró habilidad por aprender: {skill.name} (Nivel {payload.current_level} -> {payload.target_level})")
        return cls._map_to_response(saved)

    @classmethod
    async def update_learning_skill(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        learning_skill_id: uuid.UUID,
        payload: UserLearningSkillUpdate,
    ) -> UserLearningSkillResponse:
        """Actualiza los niveles y urgencia de una habilidad deseada."""
        query = (
            select(UserLearningSkill)
            .where(
                UserLearningSkill.id == learning_skill_id,
                UserLearningSkill.user_id == user_id,
            )
            .options(
                selectinload(UserLearningSkill.skill).selectinload(Skill.category)
            )
        )
        result = await db.execute(query)
        learning_skill = result.scalar_one_or_none()

        if not learning_skill:
            raise SkillMatchException(
                statuscode=status.HTTP_404_NOT_FOUND,
                message="La habilidad de aprendizaje solicitada no existe o no pertenece a tu perfil.",
            )

        # Validar consistencia de nuevos niveles
        new_current = payload.current_level if payload.current_level is not None else learning_skill.current_level
        new_target = payload.target_level if payload.target_level is not None else learning_skill.target_level

        if new_target < new_current:
            raise SkillMatchException(
                statuscode=status.HTTP_422_UNPROCESSABLE_ENTITY,
                message="El nivel meta (target_level) debe ser mayor o igual al nivel actual (current_level).",
            )

        if payload.current_level is not None:
            learning_skill.current_level = payload.current_level
        if payload.target_level is not None:
            learning_skill.target_level = payload.target_level
        if payload.urgency is not None:
            learning_skill.urgency = payload.urgency
        if payload.notes is not None:
            learning_skill.notes = payload.notes

        await db.commit()
        await db.refresh(learning_skill)
        logger.info(f"Usuario {user_id} actualizó habilidad por aprender {learning_skill_id}")
        return cls._map_to_response(learning_skill)

    @classmethod
    async def delete_learning_skill(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        learning_skill_id: uuid.UUID,
    ) -> None:
        """Elimina una habilidad de la lista de aprendizaje del miembro."""
        query = select(UserLearningSkill).where(
            UserLearningSkill.id == learning_skill_id,
            UserLearningSkill.user_id == user_id,
        )
        result = await db.execute(query)
        learning_skill = result.scalar_one_or_none()

        if not learning_skill:
            raise SkillMatchException(
                statuscode=status.HTTP_404_NOT_FOUND,
                message="La habilidad de aprendizaje solicitada no existe o no pertenece a tu perfil.",
            )

        await db.delete(learning_skill)
        await db.commit()
        logger.info(f"Usuario {user_id} eliminó habilidad por aprender {learning_skill_id}")
