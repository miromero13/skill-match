from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from pydantic import ValidationError
from app.core.deps import get_current_admin_user
from app.core.exceptions import SkillMatchException
from app.db.session import get_db
from app.models.user import User
from app.schemas.dataset_sample import DatasetSampleCreate, DatasetSampleResponse
from app.schemas.response import APIResponse
from app.services.dataset_sample_service import DatasetSampleService

router = APIRouter(
    prefix="/ai/datasets/samples",
    tags=["AI Datasets & Pilot Capture"],
    dependencies=[Depends(get_current_admin_user)],
)


@router.get(
    "",
    response_model=APIResponse[list[DatasetSampleResponse]],
    status_code=status.HTTP_200_OK,
    summary="Listar muestras de datasets de IA",
    description="Lista muestras de datasets recolectadas con paginación y conteo total. Requiere rol ADMIN.",
)
async def list_dataset_samples(
    page: int = Query(default=1, ge=1, description="Número de página"),
    page_size: int = Query(default=50, ge=1, le=100, description="Tamaño de página"),
    discipline: Optional[str] = Query(default=None, description="Filtrar por disciplina (ej. música, fútbol, programación)"),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    samples, count = await DatasetSampleService.list_samples(
        db=db,
        page=page,
        page_size=page_size,
        discipline=discipline,
    )
    return APIResponse(
        statuscode=status.HTTP_200_OK,
        message="Muestras de datasets recuperadas exitosamente.",
        data=samples,
        count=count,
    )


@router.post(
    "/upload",
    response_model=APIResponse[DatasetSampleResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Subir muestra multimedia para datasets",
    description="Subida multipart de muestras (mp4, wav, py) con verificación criptográfica de hash SHA-256. Requiere rol ADMIN.",
)
async def upload_dataset_sample(
    file: UploadFile = File(..., description="Archivo multimedia de la muestra (.mp4, .wav o .py)"),
    discipline: str = Form(..., description="Disciplina de captura (ej. música, fútbol, programación)"),
    challenge: str = Form(..., description="Reto o habilidad evaluada"),
    hardware_info: str = Form(..., description="Hardware y periféricos utilizados para la captura"),
    signed_consent: bool = Form(..., description="Consentimiento explícito firmado (debe ser true)"),
    file_hash_sha256: Optional[str] = Form(None, description="Hash SHA-256 precalculado en cliente (opcional)"),
    participant_id: Optional[str] = Form(None, description="ID del participante (fútbol)"),
    level_label: Optional[str] = Form(None, description="Nivel etiquetado (fútbol)"),
    manual_touch_count: Optional[int] = Form(None, description="Conteo manual de toques (fútbol)"),
    noise_level: Optional[str] = Form(None, description="Nivel de ruido (fútbol)"),
    surface: Optional[str] = Form(None, description="Superficie (fútbol)"),
    split: Optional[str] = Form(None, description="Partición train/val/test (fútbol)"),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    try:
        metadata = DatasetSampleCreate(
            discipline=discipline,
            challenge=challenge,
            hardware_info=hardware_info,
            signed_consent=signed_consent,
            file_hash_sha256=file_hash_sha256,
            participant_id=participant_id,
            level_label=level_label,
            manual_touch_count=manual_touch_count,
            noise_level=noise_level,
            surface=surface,
            split=split,
        )
    except ValidationError as exc:
        first_err = exc.errors()[0]
        msg = first_err.get("msg", "Error de validación en los datos de la muestra.")
        if msg.startswith("Value error, "):
            msg = msg.replace("Value error, ", "")
        raise SkillMatchException(statuscode=400, message=msg)
    sample = await DatasetSampleService.create_sample(
        db=db,
        file=file,
        metadata=metadata,
        uploaded_by_id=admin.id,
    )
    return APIResponse(
        statuscode=status.HTTP_201_CREATED,
        message="Muestra multimedia subida y procesada exitosamente.",
        data=sample,
    )


@router.delete(
    "/{sample_id}",
    response_model=APIResponse[None],
    status_code=status.HTTP_200_OK,
    summary="Eliminar muestra de dataset",
    description="Elimina una muestra defectuosa y su archivo asociado en almacenamiento estructurado. Requiere rol ADMIN.",
)
async def delete_dataset_sample(
    sample_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    await DatasetSampleService.delete_sample(db=db, sample_id=sample_id)
    return APIResponse(
        statuscode=status.HTTP_200_OK,
        message="Muestra eliminada exitosamente.",
        data=None,
    )
