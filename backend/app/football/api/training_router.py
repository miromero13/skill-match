from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_admin_user
from app.db.session import get_db
from app.football.services.synthetic_dataset_service import (
    generate_and_store_synthetic_samples,
)
from app.football.services.training_service import (
    activate_football_model_version,
    list_football_model_versions,
    train_football_level_model,
)
from app.models.user import User
from app.schemas.response import APIResponse

training_router = APIRouter(
    prefix="/training",
    tags=["Football AI Training & Dataset Generation"],
    dependencies=[Depends(get_current_admin_user)],
)


class GenerateSyntheticDatasetRequest(BaseModel):
    count: int = Field(
        default=12,
        ge=1,
        le=48,
        description="Número de muestras sintéticas a generar (1-48)",
    )
    train_ratio: float = Field(
        default=0.70,
        ge=0.1,
        le=0.9,
        description="Proporción de muestras para partición 'train'",
    )
    val_ratio: float = Field(
        default=0.15,
        ge=0.05,
        le=0.5,
        description="Proporción de muestras para partición 'val'",
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


@training_router.post(
    "/generate-synthetic",
    response_model=APIResponse[dict[str, Any]],
    status_code=status.HTTP_201_CREATED,
    summary="Generar muestras sintéticas de fútbol con física de dominadas",
)
async def generate_synthetic_dataset(
    payload: GenerateSyntheticDatasetRequest,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_current_admin_user),
) -> APIResponse[dict[str, Any]]:
    result = await generate_and_store_synthetic_samples(
        db=db,
        admin_user=admin_user,
        count=payload.count,
        train_ratio=payload.train_ratio,
        val_ratio=payload.val_ratio,
    )
    return APIResponse(
        statuscode=status.HTTP_201_CREATED,
        message=f"Se generaron y almacenaron {result['generated_count']} muestras sintéticas de fútbol exitosamente.",
        data=result,
        count=result["generated_count"],
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
