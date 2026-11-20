
import base64
from typing import Annotated, Any, Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from pydantic import BaseModel, Field, FiniteFloat, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_admin_user
from app.core.exceptions import SkillMatchException
from app.db.session import get_db
from app.models.user import User
from app.schemas.dataset_sample import DatasetSampleCreate, DatasetSampleResponse
from app.schemas.response import APIResponse
from app.services.dataset_sample_service import DatasetSampleService
from app.services.dataset_storage_service import DatasetStorageService
from app.services.flute_song_service import list_flute_songs, score_flute_song
from app.services.flute_training_service import (
    _load_sample_bytes,
    activate_flute_model,
    infer_flute,
    list_flute_model_versions,
    preview_flute_dataset,
    save_flute_labels,
    train_flute_note_model,
)

router = APIRouter(
    prefix="/ai/datasets/samples",
    tags=["AI Datasets & Pilot Capture"],
    dependencies=[Depends(get_current_admin_user)],
)


class FluteFeaturesRequest(BaseModel):
    # 48 timbre values + 14 pitch values (voiced, clarity, octaves above C5, 11 note affinities).
    audio_features: list[FiniteFloat] = Field(min_length=62, max_length=62)
    audio_schema: Literal["flute-audio-pitch-v1"]
    visual_features: list[FiniteFloat] = Field(min_length=50, max_length=50)
    visual_schema: Literal["hand-landmarks-palm-v5"]


class FluteLabelsRequest(FluteFeaturesRequest):
    participant_id: str = Field(min_length=1, max_length=100)
    note_label: str | None = None
    sound_label: str
    posture_label: str
    feature_frames: list[FluteFeaturesRequest] = Field(min_length=3, max_length=120)


class FluteInferRequest(FluteFeaturesRequest):
    target_note: str | None = None


class FlutePitchFrame(BaseModel):
    t: FiniteFloat = Field(ge=-1.0, description="Segundos desde t0 (puede ser negativo hasta -1.0 s)")
    hz: Annotated[FiniteFloat, Field(ge=0)] | None = None
    clarity: FiniteFloat = Field(ge=0, le=1)
    rms: FiniteFloat = Field(ge=0)


class FluteTimedFeatures(BaseModel):
    t: FiniteFloat
    # Exact dimensions (62 audio / 50 visual) are validated by the service.
    features: list[FiniteFloat] = Field(max_length=128)


class FluteSongScoreRequest(BaseModel):
    song_id: str = Field(min_length=1, max_length=64)
    tempo_bpm: int = Field(ge=60, le=120)
    pitch_track: list[FlutePitchFrame] = Field(max_length=4000)
    audio_schema: Literal["flute-audio-pitch-v1"]
    audio_frames: list[FluteTimedFeatures] = Field(default_factory=list, max_length=1000)
    visual_schema: Literal["hand-landmarks-palm-v5"]
    hand_frames: list[FluteTimedFeatures] = Field(default_factory=list, max_length=1000)


# Static /flute/... song routes are registered before any /{sample_id} route.
@router.get(
    "/flute/songs",
    response_model=APIResponse[list[dict[str, Any]]],
    status_code=status.HTTP_200_OK,
    summary="Listar canciones disponibles para el modo Canción de flauta",
)
async def list_flute_songs_endpoint():
    flute_songs = list_flute_songs()
    return APIResponse(
        statuscode=status.HTTP_200_OK,
        message="Canciones de flauta recuperadas exitosamente.",
        data=flute_songs,
        count=len(flute_songs),
    )


@router.post(
    "/flute/score-song",
    response_model=APIResponse[dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Evaluar una interpretación completa de una canción en flauta",
)
async def score_flute_song_endpoint(
    payload: FluteSongScoreRequest,
    db: AsyncSession = Depends(get_db),
):
    data = await score_flute_song(db=db, **payload.model_dump())
    return APIResponse(
        statuscode=status.HTTP_200_OK,
        message=data["message"],
        data=data,
    )


@router.post("/{sample_id}/flute-labels", response_model=APIResponse[dict[str, Any]])
async def save_flute_labels_endpoint(
    sample_id: UUID,
    payload: FluteLabelsRequest,
    db: AsyncSession = Depends(get_db),
):
    data = await save_flute_labels(
        db=db,
        sample_id=sample_id,
        **payload.model_dump(),
    )
    return APIResponse(
        statuscode=200,
        message="Etiquetas de flauta guardadas exitosamente.",
        data=data,
    )


@router.post("/flute/infer", response_model=APIResponse[dict[str, Any]])
async def infer_flute_endpoint(
    payload: FluteInferRequest,
    db: AsyncSession = Depends(get_db),
):
    data = await infer_flute(db=db, **payload.model_dump())
    return APIResponse(
        statuscode=200,
        message="Inferencia de flauta completada.",
        data=data,
    )


class FluteTrainModelRequest(BaseModel):
    version_tag: Optional[str] = Field(
        default=None,
        description="Etiqueta opcional de versión (ej. '1.1.0')",
    )
    activate: bool = Field(
        default=True,
        description="Activar inmediatamente como modelo de flauta en producción",
    )
    skill_id: Optional[UUID] = Field(
        default=None,
        description="ID opcional de la habilidad de flauta en el catálogo",
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
    discipline: Optional[str] = Query(
        default=None,
        description="Filtrar por disciplina (ej. música, fútbol, programación)",
    ),
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
    file: UploadFile = File(
        ...,
        description="Archivo multimedia de la muestra (.mp4, .wav o .py)",
    ),
    discipline: str = Form(
        ...,
        description="Disciplina de captura (ej. música, fútbol, programación)",
    ),
    challenge: str = Form(..., description="Reto o habilidad evaluada"),
    hardware_info: str = Form(
        ...,
        description="Hardware y periféricos utilizados para la captura",
    ),
    signed_consent: bool = Form(
        ...,
        description="Consentimiento explícito firmado (debe ser true)",
    ),
    file_hash_sha256: Optional[str] = Form(
        None,
        description="Hash SHA-256 precalculado en cliente (opcional)",
    ),
    participant_id: Optional[str] = Form(
        None,
        description="ID del participante (fútbol)",
    ),
    level_label: Optional[str] = Form(
        None,
        description="Nivel etiquetado (fútbol)",
    ),
    manual_touch_count: Optional[int] = Form(
        None,
        description="Conteo manual de toques (fútbol)",
    ),
    noise_level: Optional[str] = Form(
        None,
        description="Nivel de ruido (fútbol)",
    ),
    surface: Optional[str] = Form(
        None,
        description="Superficie (fútbol)",
    ),
    split: Optional[str] = Form(
        None,
        description="Partición train/val/test (fútbol)",
    ),
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
        msg = first_err.get(
            "msg",
            "Error de validación en los datos de la muestra.",
        )
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


@router.get(
    "/flute/preview",
    response_model=APIResponse[dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Previsualizar cobertura de notas y variaciones del dataset de flauta",
)
async def get_flute_dataset_preview(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    preview = await preview_flute_dataset(db=db)
    return APIResponse(
        statuscode=status.HTTP_200_OK,
        message="Vista previa del dataset de flauta recuperada exitosamente.",
        data=preview,
        count=preview["total_count"],
    )


@router.post(
    "/flute/train",
    response_model=APIResponse[dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Entrenar modelo clasificador de notas y postura de flauta y exportar a ONNX",
)
async def train_flute_model_endpoint(
    payload: FluteTrainModelRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    model_data = await train_flute_note_model(
        db=db,
        version_tag=payload.version_tag,
        activate=payload.activate,
        skill_id=payload.skill_id,
    )
    return APIResponse(
        statuscode=status.HTTP_200_OK,
        message=f"Modelo de flauta {model_data['version']} entrenado y exportado a ONNX exitosamente.",
        data=model_data,
    )


@router.get(
    "/flute/models",
    response_model=APIResponse[list[dict[str, Any]]],
    status_code=status.HTTP_200_OK,
    summary="Listar versiones de modelos de flauta entrenados",
)
async def list_flute_models_endpoint(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    models = await list_flute_model_versions(db=db)
    return APIResponse(
        statuscode=status.HTTP_200_OK,
        message="Modelos de flauta recuperados exitosamente.",
        data=models,
        count=len(models),
    )


@router.post(
    "/flute/models/{model_id}/activate",
    response_model=APIResponse[dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Activar una versión de modelo de flauta para validación en vivo",
)
async def activate_flute_model_endpoint(
    model_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    activated = await activate_flute_model(db=db, model_id=model_id)
    return APIResponse(
        statuscode=status.HTTP_200_OK,
        message=f"Modelo de flauta {activated['version']} activado para producción.",
        data=activated,
    )


@router.get(
    "/{sample_id}/content",
    response_model=APIResponse[dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Obtener contenido multimedia codificado para reproducir una muestra en el panel admin",
)
async def get_dataset_sample_content(
    sample_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    sample = await DatasetSampleService.get_sample(
        db=db,
        sample_id=sample_id,
    )
    raw_bytes = _load_sample_bytes(sample)

    mime_map = {
        "mp4": "video/mp4",
        "wav": "audio/wav",
        "py": "text/plain",
    }
    mime = mime_map.get(
        sample.file_format,
        "application/octet-stream",
    )
    b64 = (
        base64.b64encode(raw_bytes).decode("ascii")
        if raw_bytes
        else ""
    )
    text_preview = (
        raw_bytes.decode("utf-8", errors="replace")
        if sample.file_format == "py" and raw_bytes
        else None
    )

    return APIResponse(
        statuscode=status.HTTP_200_OK,
        message="Contenido de muestra recuperado exitosamente.",
        data={
            "id": str(sample.id),
            "file_format": sample.file_format,
            "mime_type": mime,
            "data_url": f"data:{mime};base64,{b64}" if b64 else None,
            "text_preview": text_preview,
        },
    )


@router.get(
    "/{sample_id}/preview-url",
    response_model=APIResponse[dict[str, str]],
    status_code=status.HTTP_200_OK,
    summary="Obtener URL temporal para previsualizar una muestra",
    description="Genera una URL firmada de corta duración para reproducir el archivo subido. Requiere rol ADMIN.",
)
async def get_dataset_sample_preview_url(
    sample_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    sample = await DatasetSampleService.get_sample(
        db=db,
        sample_id=sample_id,
    )
    preview_url = DatasetStorageService.get_preview_url(
        sample.storage_path,
    )

    return APIResponse(
        statuscode=status.HTTP_200_OK,
        message="URL de vista previa generada exitosamente.",
        data={
            "preview_url": preview_url,
            "file_format": sample.file_format,
        },
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
    await DatasetSampleService.delete_sample(
        db=db,
        sample_id=sample_id,
    )
    return APIResponse(
        statuscode=status.HTTP_200_OK,
        message="Muestra eliminada exitosamente.",
        data=None,
    )
