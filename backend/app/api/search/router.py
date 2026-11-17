from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import ExchangeModality, User
from app.schemas.response import APIResponse
from app.schemas.search import (
    TutorSearchFilterParams,
    TutorSearchResultItem,
)
from app.services.search_service import SearchService

router = APIRouter(prefix="/search", tags=["Búsqueda & Matching"])


@router.get(
    "/tutors",
    response_model=APIResponse[list[TutorSearchResultItem]],
    summary="Búsqueda facetada de instructores con filtros multidimensionales",
    description="Permite buscar instructores por habilidad, categoría, nivel, verificación IA, modalidad y geodistancia (HU-20 / RF-MAT-01, RF-MAT-02, RF-MAT-11).",
)
async def search_tutors(
    query: Optional[str] = Query(default=None, description="Búsqueda por texto libre"),
    skill_id: Optional[UUID] = Query(default=None, description="ID de la habilidad específica"),
    category_id: Optional[UUID] = Query(default=None, description="ID de la categoría"),
    min_level: Optional[str] = Query(
        default=None,
        description="Nivel mínimo: BEGINNER, INTERMEDIATE, ADVANCED, EXPERT",
    ),
    verified_only: bool = Query(
        default=False,
        description="Filtrar solo instructores con sello de verificación por IA",
    ),
    modality: Optional[ExchangeModality] = Query(
        default=None,
        description="Modalidad de clase: VIRTUAL, PRESENCIAL, BOTH",
    ),
    max_distance: Optional[float] = Query(
        default=None,
        ge=0.0,
        description="Radio máximo de distancia en kilómetros",
    ),
    latitude: Optional[float] = Query(
        default=None,
        ge=-90.0,
        le=90.0,
        description="Latitud de referencia del aprendiz",
    ),
    longitude: Optional[float] = Query(
        default=None,
        ge=-180.0,
        le=180.0,
        description="Longitud de referencia del aprendiz",
    ),
    sort_by: Optional[str] = Query(
        default="reputation",
        description="Orden: reputation, distance, points_asc, points_desc, experience, recent",
    ),
    page: int = Query(default=1, ge=1, description="Número de página"),
    page_size: int = Query(default=10, ge=1, le=100, description="Tamaño de página"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[list[TutorSearchResultItem]]:
    params = TutorSearchFilterParams(
        query=query,
        skill_id=skill_id,
        category_id=category_id,
        min_level=min_level,
        verified_only=verified_only,
        modality=modality,
        max_distance=max_distance,
        latitude=latitude,
        longitude=longitude,
        sort_by=sort_by,
        page=page,
        page_size=page_size,
    )

    tutors, total_count = await SearchService.search_tutors(
        db=db,
        params=params,
        reference_lat=current_user.latitude,
        reference_lon=current_user.longitude,
    )

    message = f"Se encontraron {total_count} instructores compatibles."
    return APIResponse.ok(
        data=tutors,
        message=message,
        count=total_count,
    )
