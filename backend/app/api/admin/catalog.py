import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_admin_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.catalog import (
    CategoryCreateRequest, CategoryListResponse, CategoryResponse, CategoryUpdateRequest,
    ChallengeTypeCreateRequest, ChallengeTypeListResponse, ChallengeTypeResponse,
    SkillCreateRequest, SkillListResponse, SkillResponse, SkillUpdateRequest,
    ToggleRequest, StatusRequest,
)
from app.schemas.response import APIResponse
from app.services.catalog_service import CatalogService

router = APIRouter(prefix="/admin/catalog", tags=["admin-catalog"], dependencies=[Depends(get_current_admin_user)])


@router.get("/categories", response_model=CategoryListResponse)
async def list_categories(db: AsyncSession = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    items = await CatalogService.list_categories(db)
    return CategoryListResponse(statuscode=200, message="Categorías recuperadas exitosamente.", data=items, count=len(items))


@router.post("/categories", response_model=APIResponse[CategoryResponse], status_code=status.HTTP_201_CREATED)
async def create_category(request: CategoryCreateRequest, db: AsyncSession = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    item = await CatalogService.create_category(db, request)
    return APIResponse(statuscode=201, message="Categoría creada exitosamente.", data=item)


@router.put("/categories/{category_id}", response_model=APIResponse[CategoryResponse])
async def update_category(category_id: uuid.UUID, request: CategoryUpdateRequest, db: AsyncSession = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    item = await CatalogService.update_category(db, category_id, request)
    return APIResponse(statuscode=200, message="Categoría actualizada exitosamente.", data=item)


@router.delete("/categories/{category_id}", response_model=APIResponse[None])
async def delete_category(category_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    await CatalogService.delete_category(db, category_id)
    return APIResponse(statuscode=200, message="Categoría eliminada exitosamente.", data=None)


@router.get("/challenge-types", response_model=ChallengeTypeListResponse)
async def list_challenge_types(db: AsyncSession = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    items = await CatalogService.list_challenge_types(db)
    return ChallengeTypeListResponse(statuscode=200, message="Tipos de desafío recuperados exitosamente.", data=items, count=len(items))


@router.post("/challenge-types", response_model=APIResponse[ChallengeTypeResponse], status_code=status.HTTP_201_CREATED)
async def create_challenge_type(request: ChallengeTypeCreateRequest, db: AsyncSession = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    item = await CatalogService.create_challenge_type(db, request)
    return APIResponse(statuscode=201, message="Tipo de desafío creado exitosamente.", data=item)


@router.get("/skills", response_model=SkillListResponse)
async def list_skills(category_id: uuid.UUID | None = Query(default=None), search: str | None = Query(default=None), db: AsyncSession = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    items = await CatalogService.list_skills(db, category_id=category_id, search=search)
    return SkillListResponse(statuscode=200, message="Habilidades recuperadas exitosamente.", data=items, count=len(items))


@router.post("/skills", response_model=APIResponse[SkillResponse], status_code=status.HTTP_201_CREATED)
async def create_skill(request: SkillCreateRequest, db: AsyncSession = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    item = await CatalogService.create_skill(db, request)
    return APIResponse(statuscode=201, message="Habilidad creada exitosamente.", data=item)


@router.get("/skills/{skill_id}", response_model=APIResponse[SkillResponse])
async def get_skill(skill_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    item = await CatalogService.get_skill(db, skill_id)
    return APIResponse(statuscode=200, message="Habilidad recuperada exitosamente.", data=item)


@router.put("/skills/{skill_id}", response_model=APIResponse[SkillResponse])
async def update_skill(skill_id: uuid.UUID, request: SkillUpdateRequest, db: AsyncSession = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    item = await CatalogService.update_skill(db, skill_id, request)
    return APIResponse(statuscode=200, message="Habilidad actualizada exitosamente.", data=item)


@router.patch("/skills/{skill_id}/ready", response_model=APIResponse[SkillResponse])
async def toggle_ready(skill_id: uuid.UUID, request: ToggleRequest, db: AsyncSession = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    item = await CatalogService.toggle_ready(db, skill_id, request.is_ready_to_publish)
    return APIResponse(statuscode=200, message="Estado de publicación actualizado exitosamente.", data=item)


@router.patch("/skills/{skill_id}/status", response_model=APIResponse[SkillResponse])
async def toggle_status(skill_id: uuid.UUID, request: StatusRequest, db: AsyncSession = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    item = await CatalogService.toggle_status(db, skill_id, request.is_active)
    return APIResponse(statuscode=200, message="Estado de habilidad actualizado exitosamente.", data=item)


@router.delete("/skills/{skill_id}", response_model=APIResponse[None])
async def delete_skill(skill_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    await CatalogService.delete_skill(db, skill_id)
    return APIResponse(statuscode=200, message="Habilidad eliminada exitosamente.", data=None)
