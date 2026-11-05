from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.response import APIResponse
from app.schemas.teaching_skill import (
    AvailableSkillResponse,
    TeachingSkillResponse,
    TeachingSkillWrite,
)
from app.services.teaching_skill_service import TeachingSkillService


router = APIRouter(
    prefix="/users/me/teaching-skills",
    tags=["Habilidades que enseño"],
)


@router.get(
    "/catalog",
    response_model=APIResponse[list[AvailableSkillResponse]],
    response_model_exclude_none=True,
)
async def catalog(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    skills = await TeachingSkillService.available_skills(db)
    return APIResponse.ok(
        data=[
            AvailableSkillResponse.model_validate(skill)
            for skill in skills
        ],
        message="Catálogo recuperado exitosamente.",
    )


@router.get("", response_model=APIResponse[list[TeachingSkillResponse]])
async def list_skills(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items, total = await TeachingSkillService.list_owned(
        db, user.id, page, page_size,
    )
    return APIResponse.ok(
        data=items, count=total,
        message="Habilidades recuperadas exitosamente.",
    )


@router.post(
    "",
    response_model=APIResponse[TeachingSkillResponse],
    response_model_exclude={"count"},
    status_code=201,
)
async def create_skill(
    payload: TeachingSkillWrite,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = await TeachingSkillService.save(db, user.id, payload)
    return APIResponse(
        statuscode=201,
        message="Habilidad registrada exitosamente.",
        data=item,
    )


@router.put(
    "/{item_id}",
    response_model=APIResponse[TeachingSkillResponse],
    response_model_exclude={"count"},
)
async def update_skill(
    item_id: UUID,
    payload: TeachingSkillWrite,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = await TeachingSkillService.save(db, user.id, payload, item_id)
    return APIResponse.ok(
        data=item, message="Habilidad actualizada exitosamente.",
    )


@router.delete(
    "/{item_id}",
    response_model=APIResponse[None],
    response_model_exclude={"count"},
)
async def delete_skill(
    item_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await TeachingSkillService.delete(db, user.id, item_id)
    return APIResponse.ok(message="Habilidad eliminada exitosamente.")