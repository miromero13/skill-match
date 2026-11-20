"""Per-skill training lab (admin only; members and anonymous get 404 by obfuscation).

`router` requires an ADMIN bearer. `preview_file_router` holds only the video file route, which a `<video>`
element calls without headers: it is authorized exclusively by the short-lived signed token (S10).
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import FileResponse
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
    SkillLabPreviewUrlResponse,
    SkillLabSampleResponse,
    SkillValidationResult,
)
from app.services import skill_lab_service

router = APIRouter(
    prefix="/admin/skill-lab",
    tags=["admin-skill-lab"],
    dependencies=[Depends(get_current_admin_user)],
)

# No admin dependency on purpose: the signed token is the only authorization (see module docstring).
preview_file_router = APIRouter(prefix="/admin/skill-lab", tags=["admin-skill-lab"])


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


@router.post(
    "/samples/{sample_id}/preview-url",
    response_model=APIResponse[SkillLabPreviewUrlResponse],
    summary="URL firmada (10 minutos) para reproducir el video de una muestra",
)
async def create_sample_preview_url(sample_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    data = await skill_lab_service.create_sample_preview(db, sample_id)
    return APIResponse(statuscode=200, message="URL de previsualización generada exitosamente.", data=data)


@preview_file_router.get(
    "/samples/{sample_id}/file",
    response_class=FileResponse,
    include_in_schema=False,
)
async def get_sample_preview_file(
    sample_id: str,
    token: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Streams the stored video (HTTP Range → 206). Invalid/expired/foreign token or missing file → 404."""
    path, media_type, filename = await skill_lab_service.resolve_preview_file(db, sample_id, token)
    return FileResponse(
        path,
        media_type=media_type,
        filename=filename,
        content_disposition_type="inline",
        headers={"Cache-Control": skill_lab_service.PREVIEW_CACHE_CONTROL},
    )


@router.get("/skills/{skill_id}/models", response_model=APIResponse[list[SkillLabModelResponse]])
async def list_lab_models(skill_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    models = await skill_lab_service.list_skill_models(db, skill_id)
    items = [skill_lab_service.model_to_response(model) for model in models]
    return APIResponse(statuscode=200, message="Modelos de la habilidad recuperados exitosamente.", data=items, count=len(items))


@router.post(
    "/skills/{skill_id}/train",
    response_model=APIResponse[SkillLabModelResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Entrenar (calibrar) el validador de la habilidad con los videos etiquetados",
)
async def train_lab_model(skill_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Few-shot calibration; works with zero videos (default tolerances). The new version becomes active."""
    model = await skill_lab_service.train_skill_validator(db, skill_id)
    return APIResponse(
        statuscode=201,
        message="Modelo de la habilidad entrenado exitosamente.",
        data=skill_lab_service.model_to_response(model),
    )


@router.post(
    "/skills/{skill_id}/validate",
    response_model=APIResponse[SkillValidationResult],
    summary="Validar un video contra la configuración de la habilidad (no se guarda nada)",
)
async def validate_lab_video(
    skill_id: uuid.UUID,
    file: Optional[UploadFile] = File(default=None, description="Video a validar (máximo 200 MB)"),
    skill_level_id: Optional[uuid.UUID] = Form(default=None, description="Evaluar solo este nivel (opcional)"),
    db: AsyncSession = Depends(get_db),
):
    """Always 200 for a received file: unreadable/empty/oversize videos score 0 with an explanatory note."""
    result = await skill_lab_service.validate_uploaded_video(db, skill_id, file, skill_level_id)
    return APIResponse(statuscode=200, message="Validación completada.", data=result)
