from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_admin_user
from app.db.session import get_db
from app.football.services.training_service import (
    activate_football_model_version,
    list_football_model_versions,
    preview_football_dataset,
    train_football_level_model,
)
from app.models.user import User
from app.schemas.response import APIResponse

training_router = APIRouter(
    prefix="/training",
    tags=["Football AI Training & Dataset Generation"],
    dependencies=[Depends(get_current_admin_user)],
)


class TrainModelRequest(BaseModel):
    version_tag: Optional[str] = Field(
        default=None,
        description="Etiqueta opcional de versión (ej. '1.1.0')",
    )
    activate: bool = Field(
        default=True,
        description="Activar inmediatamente como modelo en producción",
    )
    dataset_source: str = Field(
        default="all",
        description="Fuente de datos: 'all', 'real_only', 'synthetic_only', o 'custom_ids'",
    )
    sample_ids: Optional[list[UUID]] = Field(
        default=None,
        description="Lista opcional de UUIDs de muestras específicas a incluir",
    )
    skill_id: Optional[UUID] = Field(
        default=None,
        description="ID opcional de la habilidad vinculada en el catálogo",
    )


@training_router.get(
    "/dataset-preview",
    response_model=APIResponse[dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Previsualizar las muestras de dataset que se usarían al entrenar",
)
async def dataset_preview(
    dataset_source: str = Query(
        default="all",
        description="Fuente de datos a previsualizar: 'all', 'real_only', o 'synthetic_only'",
    ),
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_current_admin_user),
) -> APIResponse[dict[str, Any]]:
    preview = await preview_football_dataset(db=db, dataset_source=dataset_source)
    return APIResponse(
        statuscode=status.HTTP_200_OK,
        message="Vista previa del dataset de fútbol recuperada exitosamente.",
        data=preview,
        count=preview["total_count"],
    )


@training_router.post(
    "/train",
    response_model=APIResponse[dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Entrenar modelo de clasificación de nivel de fútbol y exportar a ONNX",
)
async def train_model(
    payload: TrainModelRequest,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_current_admin_user),
) -> APIResponse[dict[str, Any]]:
    model_data = await train_football_level_model(
        db=db,
        version_tag=payload.version_tag,
        activate=payload.activate,
        dataset_source=payload.dataset_source,
        sample_ids=payload.sample_ids,
        skill_id=payload.skill_id,
    )
    return APIResponse(
        statuscode=status.HTTP_200_OK,
        message=f"Modelo {model_data['version']} entrenado y exportado exitosamente.",
        data=model_data,
    )


@training_router.get(
    "/models",
    response_model=APIResponse[list[dict[str, Any]]],
    status_code=status.HTTP_200_OK,
    summary="Listar versiones de modelos de fútbol y sus métricas",
)
async def list_models(
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_current_admin_user),
) -> APIResponse[list[dict[str, Any]]]:
    models = await list_football_model_versions(db=db)
    return APIResponse(
        statuscode=status.HTTP_200_OK,
        message="Versiones de modelos recuperadas exitosamente.",
        data=models,
        count=len(models),
    )


@training_router.post(
    "/models/{model_id}/activate",
    response_model=APIResponse[dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Activar una versión de modelo para el validador en producción",
)
async def activate_model(
    model_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_current_admin_user),
) -> APIResponse[dict[str, Any]]:
    activated = await activate_football_model_version(db=db, model_id=model_id)
    return APIResponse(
        statuscode=status.HTTP_200_OK,
        message=f"Modelo {activated['version']} activado para producción.",
        data=activated,
    )
