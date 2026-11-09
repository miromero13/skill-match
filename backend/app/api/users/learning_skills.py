import uuid
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.response import APIResponse
from app.schemas.user_learning_skill import (
    UserLearningSkillCreate,
    UserLearningSkillUpdate,
    UserLearningSkillResponse,
)
from app.services.learning_skill_service import LearningSkillService

router = APIRouter(
    prefix="/users/me/learning-skills",
    tags=["User Learning Skills (HU-15 / RF-HAB-03)"],
)


@router.get(
    "",
    response_model=APIResponse[List[UserLearningSkillResponse]],
    status_code=status.HTTP_200_OK,
    summary="Listado de habilidades que el miembro desea aprender (HU-15 / RF-HAB-03)",
    description="Retorna las habilidades demandadas registradas por el usuario actual con nivel inicial, nivel meta y urgencia.",
)
async def list_my_learning_skills(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[List[UserLearningSkillResponse]]:
    """Consulta todas las habilidades que el usuario autenticado desea aprender."""
    items = await LearningSkillService.list_user_learning_skills(db, current_user.id)
    return APIResponse.ok(
        data=items,
        message="Habilidades deseadas recuperadas exitosamente.",
        count=len(items),
    )


@router.post(
    "",
    response_model=APIResponse[UserLearningSkillResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Registrar una habilidad para aprender (HU-15 / RF-HAB-03)",
    description="Agrega una nueva habilidad a la lista de aprendizaje del miembro validando nivel meta >= nivel actual y unicidad.",
)
async def add_learning_skill(
    payload: UserLearningSkillCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[UserLearningSkillResponse]:
    """Registra una habilidad a aprender para el miembro autenticado."""
    item = await LearningSkillService.add_learning_skill(db, current_user.id, payload)
    return APIResponse.created(
        data=item,
        message="Habilidad agregada a tu lista de aprendizaje exitosamente.",
    )


@router.put(
    "/{learning_skill_id}",
    response_model=APIResponse[UserLearningSkillResponse],
    status_code=status.HTTP_200_OK,
    summary="Actualizar niveles y urgencia de una habilidad deseada (HU-15 / RF-HAB-03)",
    description="Actualiza el nivel inicial, meta o urgencia de una habilidad en la lista de aprendizaje.",
)
async def update_learning_skill(
    learning_skill_id: uuid.UUID,
    payload: UserLearningSkillUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[UserLearningSkillResponse]:
    """Actualiza una demanda de aprendizaje del usuario."""
    item = await LearningSkillService.update_learning_skill(
        db, current_user.id, learning_skill_id, payload
    )
    return APIResponse.ok(
        data=item,
        message="Habilidad de aprendizaje actualizada exitosamente.",
    )


@router.delete(
    "/{learning_skill_id}",
    response_model=APIResponse[None],
    status_code=status.HTTP_200_OK,
    summary="Eliminar una habilidad de la lista de aprendizaje (HU-15 / RF-HAB-03)",
    description="Remueve una habilidad previamente registrada de la lista de aprendizaje del miembro.",
)
async def delete_learning_skill(
    learning_skill_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[None]:
    """Elimina una habilidad de aprendizaje del usuario."""
    await LearningSkillService.delete_learning_skill(db, current_user.id, learning_skill_id)
    return APIResponse.ok(
        data=None,
        message="Habilidad removida de tu lista de aprendizaje exitosamente.",
    )
