"""Per-skill training lab (admin only; members and anonymous get 404 by obfuscation)."""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_admin_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.response import APIResponse
from app.schemas.skill_lab import (
    MetricTypeResponse,
    SampleRole,
    SkillLabConfigResponse,
    SkillLabModelResponse,
    SkillLabSampleResponse,
)
from app.services import skill_lab_service

router = APIRouter(
    prefix="/admin/skill-lab",
    tags=["admin-skill-lab"],
    dependencies=[Depends(get_current_admin_user)],
)


@router.get("/metric-types", response_model=APIResponse[list[MetricTypeResponse]])
async def list_metric_types():
    items = skill_lab_service.METRIC_TYPES
    return APIResponse(statuscode=200, message="Tipos de métrica recuperados exitosamente.", data=items, count=len(items))


@router.get("/skills/{skill_id}", response_model=APIResponse[SkillLabConfigResponse])
async def get_lab_config(skill_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    data = await skill_lab_service.build_lab_config(db, skill_id)
    return APIResponse(statuscode=200, message="Configuración del laboratorio recuperada exitosamente.", data=data)


@router.post(
    "/skills/{skill_id}/samples",
    response_model=APIResponse[SkillLabSampleResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Subir video de entrenamiento o de referencia vinculado a un nivel y criterio",
)
async def upload_lab_sample(
    skill_id: uuid.UUID,
    file: UploadFile = File(..., description="Video .mp4, .webm o .mov (máximo 200 MB)"),
    skill_level_id: uuid.UUID = Form(..., description="Nivel de la habilidad al que pertenece el video"),
    sample_role: str = Form("TRAINING", description="TRAINING (dataset) o REFERENCE (video a replicar)"),
    criterion_key: Optional[str] = Form(None, description="Clave del criterio del nivel (opcional)"),
    participant_id: Optional[str] = Form(None, description="Identificador anónimo del participante"),
    signed_consent: bool = Form(..., description="Consentimiento informado firmado (debe ser true)"),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    sample = await skill_lab_service.create_lab_sample(
        db,
        skill_id=skill_id,
        upload=file,
        skill_level_id=skill_level_id,
        sample_role=sample_role,
        criterion_key=criterion_key,
        participant_id=participant_id,
        signed_consent=signed_consent,
        uploaded_by_id=admin.id,
    )
    return APIResponse(
        statuscode=201,
        message="Muestra del laboratorio subida exitosamente.",
        data=skill_lab_service.sample_to_response(sample),
    )


@router.get("/skills/{skill_id}/samples", response_model=APIResponse[list[SkillLabSampleResponse]])
async def list_lab_samples(
    skill_id: uuid.UUID,
    sample_role: Optional[SampleRole] = Query(default=None, description="Filtrar por TRAINING o REFERENCE"),
    db: AsyncSession = Depends(get_db),
):
    await skill_lab_service.load_skill_for_lab(db, skill_id)
    samples = await skill_lab_service.list_skill_samples(db, skill_id, role=sample_role)
    items = [skill_lab_service.sample_to_response(sample) for sample in samples]
    return APIResponse(statuscode=200, message="Muestras del laboratorio recuperadas exitosamente.", data=items, count=len(items))


@router.delete("/samples/{sample_id}", response_model=APIResponse[None])
async def delete_lab_sample(sample_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    await skill_lab_service.delete_lab_sample(db, sample_id)
    return APIResponse(statuscode=200, message="Muestra eliminada exitosamente.", data=None)


@router.get("/skills/{skill_id}/models", response_model=APIResponse[list[SkillLabModelResponse]])
async def list_lab_models(skill_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    models = await skill_lab_service.list_skill_models(db, skill_id)
    items = [skill_lab_service.model_to_response(model) for model in models]
    return APIResponse(statuscode=200, message="Modelos de la habilidad recuperados exitosamente.", data=items, count=len(items))
