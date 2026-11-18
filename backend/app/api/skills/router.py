import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.catalog import CategoryResponse, SkillResponse
from app.schemas.response import APIResponse
from app.services.catalog_service import CatalogService

router = APIRouter(prefix="", tags=["Public Catalog (HU-12 / HU-15)"])


@router.get(
    "/skills", response_model=APIResponse[List[SkillResponse]], status_code=status.HTTP_200_OK,
    summary="Catálogo de habilidades activas (HU-12 / HU-15)",
    description="Consulta pública: excluye habilidades inactivas y categorías con cualquier ancestro inactivo.",
)
async def list_skills(
    category_id: Optional[uuid.UUID] = Query(None, description="Categoría y sus subcategorías"),
    search: Optional[str] = Query(None, description="Búsqueda por nombre de habilidad"),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[List[SkillResponse]]:
    items = await CatalogService.list_skills(db, category_id, search, public_only=True)
    return APIResponse.ok(data=items, message="Habilidades del catálogo recuperadas exitosamente.", count=len(items))


@router.get(
    "/skills/{skill_id}", response_model=APIResponse[SkillResponse],
    summary="Detalle público de una habilidad activa (HU-12)",
)
async def get_skill(skill_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> APIResponse[SkillResponse]:
    item = await CatalogService.get_skill(db, skill_id, public_only=True)
    return APIResponse.ok(data=item, message="Habilidad recuperada exitosamente.")


@router.get(
    "/categories", response_model=APIResponse[List[CategoryResponse]], status_code=status.HTTP_200_OK,
    summary="Categorías y subcategorías activas del catálogo",
)
async def list_categories(db: AsyncSession = Depends(get_db)) -> APIResponse[List[CategoryResponse]]:
    items = await CatalogService.list_categories(db, public_only=True)
    return APIResponse.ok(data=items, message="Categorías recuperadas exitosamente.", count=len(items))
