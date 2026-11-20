"""
Per-skill training lab (S2-S4): reads every parameter from the catalog skill and manages the
datasets (TRAINING) and reference videos (REFERENCE) linked to each level and criterion.

Training/validation (S5/S6) build on `load_skill_for_lab`, `level_criteria`, `list_skill_samples`
and `sample_local_path`; they are not implemented here.
"""
import asyncio
import hashlib
import logging
import uuid
from pathlib import Path
from typing import Any, Optional

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import SkillMatchException
from app.football.models import ModelVersion
from app.football.services.storage import garage_s3_storage
from app.models.catalog import Skill, SkillLevel
from app.models.dataset_sample import DatasetSample
from app.schemas.catalog import (
    METRIC_BALL_TOUCH_STREAK,
    METRIC_REFERENCE_REPLICATION,
    RubricCriterionSchema,
    RubricSchema,
)
from app.schemas.skill_lab import SkillLabModelResponse, SkillLabSampleResponse
from app.services.catalog_service import (
    ball_target_message,
    weights_total_is_valid,
    weights_total_message,
)
from app.services.dataset_storage_service import DatasetStorageService

logger = logging.getLogger("skillmatch.skill_lab")

SKILL_VALIDATOR_MODEL_NAME = "skill_validator"
SAMPLE_ROLE_TRAINING = "TRAINING"
SAMPLE_ROLE_REFERENCE = "REFERENCE"
SAMPLE_ROLES = (SAMPLE_ROLE_TRAINING, SAMPLE_ROLE_REFERENCE)
SKILL_LAB_HARDWARE_INFO = "skill-lab-upload"
SKILL_LAB_STORAGE_SUBDIR = "skill-lab"
SKILL_LAB_ALLOWED_EXTENSIONS = {"mp4", "webm", "mov"}
SKILL_LAB_MAX_FILE_SIZE_MB = 200
SKILL_LAB_MAX_FILE_SIZE_BYTES = SKILL_LAB_MAX_FILE_SIZE_MB * 1024 * 1024
_CHUNK_SIZE = 1024 * 1024
_CONTENT_TYPES = {"mp4": "video/mp4", "webm": "video/webm", "mov": "video/quicktime"}

# Hardcoded until the engine (`app.skill_validation.METRIC_TYPES`) is wired in by T4.
METRIC_TYPES: list[dict[str, Any]] = [
    {
        "code": METRIC_REFERENCE_REPLICATION,
        "name": "Réplica del video de referencia",
        "description": (
            "Compara los movimientos del usuario con el video de referencia del nivel (o del criterio), "
            "tolerando diferencias de ángulo de cámara, lateralidad y ritmo."
        ),
        "requires_target": False,
        "requires_reference": True,
    },
    {
        "code": METRIC_BALL_TOUCH_STREAK,
        "name": "Racha de toques de balón",
        "description": (
            "Cuenta los toques consecutivos sin que el balón caiga; el objetivo (target) es la cantidad "
            "de toques seguidos que vale el 100% del criterio."
        ),
        "requires_target": True,
        "requires_reference": False,
    },
]


def _not_found(message: str) -> SkillMatchException:
    return SkillMatchException(statuscode=404, message=message)


def _bad_request(message: str) -> SkillMatchException:
    return SkillMatchException(statuscode=400, message=message)


# ------------------------------------------------------------------ catalog reads (reused by T4)


async def load_skill_for_lab(db: AsyncSession, skill_id: uuid.UUID) -> Skill:
    """Skill with category, challenge type, levels and rubrics eagerly loaded (read-only, no repair)."""
    stmt = (
        select(Skill)
        .options(
            selectinload(Skill.category),
            selectinload(Skill.challenge_type),
            selectinload(Skill.levels).selectinload(SkillLevel.rubric),
        )
        .where(Skill.id == skill_id)
    )
    skill = (await db.execute(stmt)).scalar_one_or_none()
    if skill is None:
        raise _not_found("Habilidad no encontrada")
    return skill


def level_criteria(level: SkillLevel) -> list[RubricCriterionSchema]:
    """Normalized criteria of a level: same keys/defaults the catalog API returns (legacy keys included)."""
    if level.rubric is None:
        return []
    return RubricSchema.model_validate({"criteria": level.rubric.criteria or []}).criteria


def level_min_score(level: SkillLevel) -> float:
    return float(level.rubric.min_score) if level.rubric is not None else 70.0


async def list_skill_samples(
    db: AsyncSession, skill_id: uuid.UUID, role: Optional[str] = None
) -> list[DatasetSample]:
    """Lab samples of a skill (newest first), optionally filtered by `sample_role`."""
    stmt = select(DatasetSample).where(DatasetSample.skill_id == skill_id)
    if role is not None:
        stmt = stmt.where(DatasetSample.sample_role == role)
    stmt = stmt.order_by(DatasetSample.created_at.desc(), DatasetSample.id.asc())
    return list((await db.execute(stmt)).scalars().all())


def sample_local_path(sample: DatasetSample) -> Path:
    """Local copy of a stored sample (kept even when it was replicated to Garage S3)."""
    key = sample.storage_path
    if key.startswith("s3://"):
        parts = key.replace("s3://", "", 1).split("/", 1)
        key = parts[1] if len(parts) > 1 else ""
    return DatasetStorageService.get_base_storage_dir().parent / key


def sample_to_response(sample: DatasetSample) -> SkillLabSampleResponse:
    analysis = sample.analysis if isinstance(sample.analysis, dict) else None
    notes = analysis.get("notes") if analysis else None
    return SkillLabSampleResponse(
        id=sample.id,
        skill_id=sample.skill_id,
        skill_level_id=sample.skill_level_id,
        criterion_key=sample.criterion_key,
        sample_role=sample.sample_role,
        file_format=sample.file_format,
        file_size_bytes=sample.file_size_bytes,
        participant_id=sample.participant_id,
        analysis_ready=analysis is not None,
        analysis_notes=[str(note) for note in notes] if isinstance(notes, list) else [],
        created_at=sample.created_at,
    )


def model_to_response(model: ModelVersion) -> SkillLabModelResponse:
    return SkillLabModelResponse(
        id=model.id,
        skill_id=model.skill_id,
        version=model.version,
        activa=model.activa,
        metricas=model.metricas or {},
        created_at=model.created_at,
    )


async def list_skill_models(db: AsyncSession, skill_id: uuid.UUID) -> list[ModelVersion]:
    await load_skill_for_lab(db, skill_id)
    stmt = (
        select(ModelVersion)
        .where(ModelVersion.skill_id == skill_id, ModelVersion.nombre == SKILL_VALIDATOR_MODEL_NAME)
        .order_by(ModelVersion.activa.desc(), ModelVersion.created_at.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def get_active_skill_model(db: AsyncSession, skill_id: uuid.UUID) -> Optional[ModelVersion]:
    stmt = (
        select(ModelVersion)
        .where(
            ModelVersion.skill_id == skill_id,
            ModelVersion.nombre == SKILL_VALIDATOR_MODEL_NAME,
            ModelVersion.activa.is_(True),
        )
        .order_by(ModelVersion.created_at.desc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


# ------------------------------------------------------------------ lab configuration (S2)


def _readiness_issues(skill: Skill, references: dict[tuple, DatasetSample]) -> list[str]:
    if not skill.levels:
        return ["La habilidad no tiene niveles configurados."]
    issues: list[str] = []
    for level in skill.levels:
        criteria = level_criteria(level)
        if criteria and not weights_total_is_valid(sum(c.weight for c in criteria)):
            issues.append(weights_total_message(level.name, sum(c.weight for c in criteria)))
        for criterion in criteria:
            if criterion.metric_type == METRIC_BALL_TOUCH_STREAK and criterion.target is None:
                issues.append(ball_target_message(criterion.name, level.name))
        # A level without criteria is evaluated as one implicit REFERENCE_REPLICATION criterion.
        needs_level_reference = not criteria or any(
            c.metric_type == METRIC_REFERENCE_REPLICATION and (level.id, c.key) not in references
            for c in criteria
        )
        if needs_level_reference and (level.id, None) not in references:
            issues.append(f"El nivel «{level.name}» no tiene video de referencia.")
    return issues


async def build_lab_config(db: AsyncSession, skill_id: uuid.UUID) -> dict[str, Any]:
    skill = await load_skill_for_lab(db, skill_id)
    count_rows = await db.execute(
        select(DatasetSample.skill_level_id, DatasetSample.criterion_key, func.count())
        .where(DatasetSample.skill_id == skill_id, DatasetSample.sample_role == SAMPLE_ROLE_TRAINING)
        .group_by(DatasetSample.skill_level_id, DatasetSample.criterion_key)
    )
    training: dict[tuple, int] = {(level_id, key): count for level_id, key, count in count_rows.all()}
    references: dict[tuple, DatasetSample] = {}
    for sample in await list_skill_samples(db, skill_id, role=SAMPLE_ROLE_REFERENCE):
        # Newest first: keep the latest one if older duplicates ever exist.
        references.setdefault((sample.skill_level_id, sample.criterion_key), sample)

    levels = []
    for level in skill.levels:
        criteria = level_criteria(level)
        level_reference = references.get((level.id, None))
        levels.append({
            "id": level.id,
            "level_number": level.level_number,
            "name": level.name,
            "min_score": level_min_score(level),
            "weights_total": round(sum(c.weight for c in criteria), 2),
            "criteria": [
                {
                    **criterion.model_dump(),
                    "training_samples": training.get((level.id, criterion.key), 0),
                    "has_reference": (level.id, criterion.key) in references,
                }
                for criterion in criteria
            ],
            "training_samples": sum(count for (level_id, _), count in training.items() if level_id == level.id),
            "reference": sample_to_response(level_reference) if level_reference else None,
        })

    issues = _readiness_issues(skill, references)
    active = await get_active_skill_model(db, skill_id)
    challenge = skill.challenge_type
    return {
        "skill": {
            "id": skill.id,
            "name": skill.name,
            "category": {"id": skill.category.id, "name": skill.category.name},
            "challenge_type": (
                {"id": challenge.id, "name": challenge.name, "code": challenge.code,
                 "evaluation_modality": challenge.evaluation_modality}
                if challenge is not None else None
            ),
            "min_approval_threshold": skill.min_approval_threshold,
        },
        "levels": levels,
        "active_model": model_to_response(active) if active else None,
        "readiness": {"ready_to_validate": not issues, "issues": issues},
    }


# ------------------------------------------------------------------ samples (S3, S4)


def _clean_path_segment(value: str) -> str:
    return "".join(char for char in value.lower() if char.isalnum() or char in "-_") or "general"


async def _replicate_to_s3(local_path: Path, object_key: str, ext: str, sha256_hex: str) -> Optional[str]:
    """Stream the stored file to Garage S3 when configured; None keeps the local path as storage."""
    if not (garage_s3_storage.access_key_id and garage_s3_storage.secret_access_key):
        return None
    try:
        client = garage_s3_storage._build_s3_client()
        await asyncio.to_thread(
            client.upload_file,
            str(local_path),
            garage_s3_storage.bucket_name,
            object_key,
            ExtraArgs={"ContentType": _CONTENT_TYPES.get(ext, "application/octet-stream"),
                       "Metadata": {"sha256": sha256_hex}},
        )
        return f"s3://{garage_s3_storage.bucket_name}/{object_key}"
    except Exception as exc:  # noqa: BLE001 - replication is best effort, local copy remains.
        logger.warning("No se pudo replicar la muestra del laboratorio en Garage S3 (%s); usando ruta local.", exc)
        return None


async def _store_lab_video(upload: UploadFile, sample_id: uuid.UUID, discipline: str) -> tuple[str, str, int, str]:
    """Stream the upload to the dataset storage (SHA-256 on the fly, size cap); returns path/hash/size/ext."""
    filename = upload.filename or "sample"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in SKILL_LAB_ALLOWED_EXTENSIONS:
        raise _bad_request(
            f"Formato no permitido: '.{ext}'. Solo se permiten archivos "
            f"{', '.join(sorted(SKILL_LAB_ALLOWED_EXTENSIONS))}."
        )
    segment = _clean_path_segment(discipline)
    dest_dir = DatasetStorageService.get_base_storage_dir() / SKILL_LAB_STORAGE_SUBDIR / segment
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f"{sample_id}.{ext}"
    object_key = f"datasets/{SKILL_LAB_STORAGE_SUBDIR}/{segment}/{sample_id}.{ext}"

    hasher = hashlib.sha256()
    total = 0
    try:
        with open(dest_path, "wb") as buffer:
            while chunk := await upload.read(_CHUNK_SIZE):
                total += len(chunk)
                if total > SKILL_LAB_MAX_FILE_SIZE_BYTES:
                    raise _bad_request(
                        f"El tamaño del archivo supera el límite máximo permitido de {SKILL_LAB_MAX_FILE_SIZE_MB} MB."
                    )
                hasher.update(chunk)
                buffer.write(chunk)
        if total == 0:
            raise _bad_request("El archivo de video está vacío.")
    except BaseException:
        dest_path.unlink(missing_ok=True)
        raise

    sha256_hex = hasher.hexdigest()
    storage_path = await _replicate_to_s3(dest_path, object_key, ext, sha256_hex) or object_key
    return storage_path, sha256_hex, total, ext


def _find_level(skill: Skill, level_id: uuid.UUID) -> SkillLevel:
    level = next((item for item in skill.levels if item.id == level_id), None)
    if level is None:
        raise _not_found("Nivel no encontrado para esta habilidad.")
    return level


async def create_lab_sample(
    db: AsyncSession,
    *,
    skill_id: uuid.UUID,
    upload: UploadFile,
    skill_level_id: uuid.UUID,
    sample_role: str,
    criterion_key: Optional[str],
    participant_id: Optional[str],
    signed_consent: bool,
    uploaded_by_id: Optional[uuid.UUID],
) -> DatasetSample:
    skill = await load_skill_for_lab(db, skill_id)
    level = _find_level(skill, skill_level_id)
    criterion_key = (criterion_key or "").strip() or None
    if criterion_key is not None and criterion_key not in {c.key for c in level_criteria(level)}:
        raise _bad_request(f"El criterio indicado no existe en el nivel «{level.name}».")
    role = (sample_role or "").strip().upper()
    if role not in SAMPLE_ROLES:
        raise _bad_request("El rol de la muestra debe ser TRAINING o REFERENCE.")
    if not signed_consent:
        raise _bad_request("El consentimiento informado firmado es obligatorio.")
    participant_id = (participant_id or "").strip() or None
    if participant_id is not None and len(participant_id) > 100:
        raise _bad_request("El identificador del participante no puede superar 100 caracteres.")

    discipline = (skill.category.slug or skill.category.name)[:50]
    sample_id = uuid.uuid4()
    storage_path, sha256_hex, size, ext = await _store_lab_video(upload, sample_id, discipline)

    replaced: list[DatasetSample] = []
    if role == SAMPLE_ROLE_REFERENCE:
        # S4: one active reference per (level, criterion or level-wide); the new one replaces it.
        stmt = select(DatasetSample).where(
            DatasetSample.skill_id == skill.id,
            DatasetSample.skill_level_id == level.id,
            DatasetSample.sample_role == SAMPLE_ROLE_REFERENCE,
            DatasetSample.criterion_key.is_(None) if criterion_key is None
            else DatasetSample.criterion_key == criterion_key,
        )
        replaced = list((await db.execute(stmt)).scalars().all())

    sample = DatasetSample(
        id=sample_id,
        discipline=discipline,
        challenge=skill.name[:100],
        hardware_info=SKILL_LAB_HARDWARE_INFO,
        signed_consent=True,
        file_format=ext,
        file_size_bytes=size,
        file_hash_sha256=sha256_hex,
        storage_path=storage_path,
        uploaded_by_id=uploaded_by_id,
        participant_id=participant_id,
        level_label=level.name[:50],
        skill_id=skill.id,
        skill_level_id=level.id,
        criterion_key=criterion_key,
        sample_role=role,
        analysis=None,
    )
    old_paths = [item.storage_path for item in replaced]
    try:
        for item in replaced:
            await db.delete(item)
        db.add(sample)
        await db.commit()
    except Exception:
        await db.rollback()
        DatasetStorageService.delete_file(storage_path)
        raise
    for path in old_paths:
        DatasetStorageService.delete_file(path)
    await db.refresh(sample)
    return sample


async def delete_lab_sample(db: AsyncSession, sample_id: uuid.UUID) -> None:
    sample = (
        await db.execute(
            select(DatasetSample).where(DatasetSample.id == sample_id, DatasetSample.skill_id.is_not(None))
        )
    ).scalar_one_or_none()
    if sample is None:
        raise _not_found("Muestra no encontrada.")
    storage_path = sample.storage_path
    await db.delete(sample)
    await db.commit()
    DatasetStorageService.delete_file(storage_path)
