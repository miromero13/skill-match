import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.catalog import Category, Skill, SkillLevel
from app.schemas.catalog import CategoryResponse, SkillResponse
from app.schemas.response import APIResponse

router = APIRouter(prefix="", tags=["Public Catalog (HU-12 / HU-15)"])


@router.get(
    "/skills",
    response_model=APIResponse[List[SkillResponse]],
    status_code=status.HTTP_200_OK,
    summary="Catálogo de habilidades (HU-12 / HU-15)",
)
async def list_skills(
    category_id: Optional[uuid.UUID] = Query(None, description="Filtrar por categoría"),
    search: Optional[str] = Query(None, description="Búsqueda por nombre de habilidad"),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[List[SkillResponse]]:
    stmt = (
        select(Skill)
        .options(
            selectinload(Skill.levels).selectinload(SkillLevel.rubric),
            selectinload(Skill.challenge_type),
        )
        .order_by(Skill.name)
    )
    if category_id:
        stmt = stmt.where(Skill.category_id == category_id)
    if search and search.strip():
        stmt = stmt.where(Skill.name.ilike(f"%{search.strip()}%"))

    result = await db.execute(stmt)
    items = list(result.scalars().all())
    return APIResponse.ok(
        data=items,
        message="Habilidades del catálogo recuperadas exitosamente.",
        count=len(items),
    )


@router.get(
    "/categories",
    response_model=APIResponse[List[CategoryResponse]],
    status_code=status.HTTP_200_OK,
    summary="Listado de categorías del catálogo",
)
async def list_categories(
    db: AsyncSession = Depends(get_db),
) -> APIResponse[List[CategoryResponse]]:
    stmt = select(Category).order_by(Category.name)
    result = await db.execute(stmt)
    items = list(result.scalars().all())
    return APIResponse.ok(
        data=items,
        message="Categorías recuperadas exitosamente.",
        count=len(items),
    )
