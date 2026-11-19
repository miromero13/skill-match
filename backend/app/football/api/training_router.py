from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_admin_user
from app.db.session import get_db
from app.football.services.training_service import (
    activate_football_model_version,
    list_football_model_versions,
    preview_football_dataset,
)
from app.football.tasks import celery_app, train_level_model_task
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
        description=(
            "Fuente de datos: 'all' (todas las muestras reales de fútbol) o "
            "'custom_ids' (solo las indicadas en sample_ids). El entrenamiento usa "
            "únicamente muestras reales; no existe camino sintético."
        ),
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
    status_code=status.HTTP_202_ACCEPTED,
    summary="Encolar el entrenamiento del clasificador de nivel de fútbol (ONNX)",
)
async def train_model(
    payload: TrainModelRequest,
    admin_user: User = Depends(get_current_admin_user),
) -> APIResponse[dict[str, Any]]:
    async_result = train_level_model_task.delay(
        version_tag=payload.version_tag,
        activate=payload.activate,
        dataset_source=payload.dataset_source,
        sample_ids=[str(i) for i in payload.sample_ids] if payload.sample_ids else None,
        skill_id=str(payload.skill_id) if payload.skill_id else None,
    )
    return APIResponse(
        statuscode=status.HTTP_202_ACCEPTED,
        message="Entrenamiento encolado.",
        data={"task_id": str(async_result.id)},
    )


@training_router.get(
    "/train/{task_id}/status",
    response_model=APIResponse[dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Consultar el estado y progreso de un entrenamiento encolado",
)
async def train_model_status(
    task_id: str,
    admin_user: User = Depends(get_current_admin_user),
) -> APIResponse[dict[str, Any]]:
    async_result = AsyncResult(task_id, app=celery_app)
    state = async_result.state
    data: dict[str, Any] = {
        "status": "queued",
        "processed": None,
        "total": None,
        "message": None,
        "result": None,
    }
    if state == "PROGRESS":
        meta = async_result.info if isinstance(async_result.info, dict) else {}
        data.update(
            status="running",
            processed=meta.get("processed"),
            total=meta.get("total"),
            message=meta.get("message"),
        )
    elif state == "SUCCESS":
        data.update(status="done", result=async_result.result)
    elif state == "FAILURE":
        error = async_result.result
        data.update(
            status="failed",
            message=str(error) if isinstance(error, BaseException) else None,
        )
    elif state in ("STARTED", "RETRY"):
        data.update(status="running")
    return APIResponse(
        statuscode=status.HTTP_200_OK,
        message="Estado del entrenamiento recuperado.",
        data=data,
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
