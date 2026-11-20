"""
Per-skill training lab (S2-S7): reads every parameter from the catalog skill, manages the datasets
(TRAINING) and reference videos (REFERENCE) linked to each level and criterion, caches the engine
analysis of every sample, trains (few-shot calibration) one `skill_validator` per skill and validates
videos with `app.skill_validation`.

`validate_skill_video(db, skill_id, video_path, target_level_id=None)` is the single entry point the
member-facing flow must call; the admin `/validate` endpoint is a thin upload wrapper around it.
"""
import asyncio
import hashlib
import hmac
import logging
import os
import re
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import UploadFile
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
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
from app.skill_validation import (
    ENGINE_VERSION,
    METRIC_TYPES as ENGINE_METRIC_TYPES,
    CriterionSpec,
    LabeledSample,
    LevelSpec,
    SkillSpec,
    analyze_video,
    calibrate_skill,
    evaluate_skill,
)
from app.skill_validation import similarity
from app.skill_validation.analysis import (
    BALL_NOT_REQUESTED,
    BALL_OK,
    NOTE_UNREADABLE,
    POSE_MODEL_UNAVAILABLE,
    POSE_NOT_REQUESTED,
    POSE_OK,
    POSE_UNREADABLE,
)

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

# Single source of truth: the engine's metric catalog (codes, Spanish names, requirements).
METRIC_TYPES: list[dict[str, Any]] = ENGINE_METRIC_TYPES

# Calibration JSON lives in the model row itself (`metricas["calibration"]`, PostgreSQL), so it is
# atomic with the version/activation and survives container restarts without a storage volume.
# `ruta_onnx` is a legacy NOT NULL column; this sentinel documents where the artifact is.
CALIBRATION_METRICS_KEY = "calibration"
CALIBRATION_STORAGE_REF = "db:model_versions.metricas.calibration"

NOTE_NO_FILE = "No se recibió ningún archivo de video."
NOTE_EMPTY_FILE = "El archivo recibido está vacío."
NOTE_OVERSIZE = f"El video supera el tamaño máximo de {SKILL_LAB_MAX_FILE_SIZE_MB} MB; no se analizó."
NOTE_RECEIVE_FAILED = "Ocurrió un fallo interno al recibir el video; no se analizó."
NOTE_ANALYSIS_FAILED = "Ocurrió un fallo interno al analizar el video; no se otorgó aprobación."
_VALIDATE_ALLOWED_SUFFIXES = {".mp4", ".webm", ".mov", ".m4v", ".mkv", ".avi"}


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
    if analysis is not None and analysis.get("engine_version") != ENGINE_VERSION:
        analysis = None  # stale: recomputed lazily by train/validate
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
    metrics = {key: value for key, value in (model.metricas or {}).items() if key != CALIBRATION_METRICS_KEY}
    return SkillLabModelResponse(
        id=model.id,
        skill_id=model.skill_id,
        version=model.version,
        activa=model.activa,
        metricas=metrics,
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


def reference_pose_usable(analysis: Any) -> bool:
    """Same rule the engine applies to a reference: a parsable pose with enough detected frames."""
    if not isinstance(analysis, dict):
        return False
    sequence = similarity.parse_pose(analysis.get("pose"))
    return sequence is not None and len(sequence.angles) >= similarity.MIN_POSE_FRAMES


def _reference_unusable(sample: DatasetSample) -> bool:
    """A current analysis proves the reference has no usable pose (pending analyses are not issues)."""
    analysis = sample.analysis
    if not isinstance(analysis, dict) or analysis.get("engine_version") != ENGINE_VERSION:
        return False
    if analysis.get("pose_status") in (POSE_NOT_REQUESTED, POSE_MODEL_UNAVAILABLE):
        return False  # recomputed lazily (pass missing or model installed later)
    return not reference_pose_usable(analysis)


def _readiness_issues(skill: Skill, references: dict[tuple, DatasetSample]) -> list[str]:
    """Every level must be evaluable: valid weights/targets and a usable reference wherever one is required."""
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
        replication = [c for c in criteria if c.metric_type == METRIC_REFERENCE_REPLICATION]
        own_references = [(c, references[(level.id, c.key)]) for c in replication if (level.id, c.key) in references]
        needs_level_reference = not criteria or len(own_references) < len(replication)
        level_reference = references.get((level.id, None))
        if needs_level_reference and level_reference is None:
            issues.append(f"El nivel «{level.name}» no tiene video de referencia.")
        elif needs_level_reference and _reference_unusable(level_reference):
            issues.append(
                f"El video de referencia del nivel «{level.name}» no tiene una pose utilizable; vuelve a subirlo."
            )
        for criterion, sample in own_references:
            if _reference_unusable(sample):
                issues.append(
                    f"El video de referencia del criterio «{criterion.name}» del nivel «{level.name}» no tiene "
                    "una pose utilizable; vuelve a subirlo."
                )
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
    await _analyze_new_sample(db, skill, sample)
    return sample


async def _analyze_new_sample(db: AsyncSession, skill: Skill, sample: DatasetSample) -> None:
    """Cache the engine analysis right after the upload; any failure leaves it pending (never fails the upload)."""
    need_pose, need_ball = sample_analysis_needs(skill, sample)
    try:
        sample.analysis = await _run_analysis(sample_local_path(sample), need_pose, need_ball)
        await db.commit()
    except Exception:  # noqa: BLE001 - the sample is stored; train/validate recompute it lazily.
        logger.exception("No se pudo analizar la muestra %s del laboratorio; queda pendiente.", sample.id)
        try:
            await db.rollback()
        except Exception:  # noqa: BLE001
            logger.exception("Rollback failed after a lab sample analysis error")
    try:
        await db.refresh(sample)
    except Exception:  # noqa: BLE001 - the response is built from the in-memory row
        logger.exception("Could not refresh lab sample %s", sample.id)


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


# ------------------------------------------------------------------ playback (S10)
#
# A `<video>` element cannot send the Authorization header, so the admin mints a short-lived URL whose
# token is an HMAC-SHA256 (SECRET_KEY) over purpose|sample_id|expires_epoch. The file route is authorized
# only by that token; anything invalid answers the same 404 as the admin routes (AGENTS.md §1.3).

PREVIEW_TOKEN_TTL_SECONDS = 600
PREVIEW_TOKEN_PURPOSE = "skill-lab-preview"
PREVIEW_CACHE_CONTROL = f"private, max-age={PREVIEW_TOKEN_TTL_SECONDS}"
NOT_FOUND_MESSAGE = "Recurso no encontrado"
SAMPLE_NOT_FOUND_MESSAGE = "Muestra no encontrada."
SAMPLE_FILE_UNAVAILABLE_MESSAGE = "El video de la muestra no está disponible."


def _preview_signature(sample_id: uuid.UUID, expires: int) -> str:
    message = f"{PREVIEW_TOKEN_PURPOSE}|{sample_id}|{expires}".encode()
    key = settings.SECRET_KEY.get_secret_value().encode()
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def sign_preview_token(sample_id: uuid.UUID, expires: int) -> str:
    """Token `<expires_epoch>.<hex hmac>` bound to one sample."""
    return f"{expires}.{_preview_signature(sample_id, expires)}"


def preview_token_is_valid(sample_id: uuid.UUID, token: Optional[str]) -> bool:
    if not token or "." not in token:
        return False
    expires_raw, signature = token.split(".", 1)
    if not (expires_raw.isascii() and expires_raw.isdigit()):
        return False
    expires = int(expires_raw)
    if not hmac.compare_digest(signature, _preview_signature(sample_id, expires)):
        return False
    return time.time() < expires


async def _get_lab_sample(db: AsyncSession, sample_id: uuid.UUID) -> Optional[DatasetSample]:
    stmt = select(DatasetSample).where(DatasetSample.id == sample_id, DatasetSample.skill_id.is_not(None))
    return (await db.execute(stmt)).scalar_one_or_none()


def sample_playable_file(sample: DatasetSample) -> Optional[tuple[Path, str]]:
    """(path, media type) of the sample's local copy, only if it is a file inside the storage root."""
    media_type = _CONTENT_TYPES.get((sample.file_format or "").lower())
    if media_type is None:
        return None
    root = DatasetStorageService.get_base_storage_dir().parent.resolve()
    path = sample_local_path(sample).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        return None
    return path, media_type


async def create_sample_preview(db: AsyncSession, sample_id: uuid.UUID) -> dict[str, Any]:
    sample = await _get_lab_sample(db, sample_id)
    if sample is None:
        raise _not_found(SAMPLE_NOT_FOUND_MESSAGE)
    playable = sample_playable_file(sample)
    if playable is None:
        raise _not_found(SAMPLE_FILE_UNAVAILABLE_MESSAGE)
    expires = int(time.time()) + PREVIEW_TOKEN_TTL_SECONDS
    return {
        "url": f"/api/admin/skill-lab/samples/{sample.id}/file?token={sign_preview_token(sample.id, expires)}",
        "expires_at": datetime.fromtimestamp(expires, tz=timezone.utc),
        "content_type": playable[1],
    }


async def resolve_preview_file(
    db: AsyncSession, sample_id: str, token: Optional[str]
) -> tuple[Path, str, str]:
    """(path, media type, safe filename) for a valid token; every failure is the obfuscated 404."""
    try:
        parsed_id = uuid.UUID(sample_id)
    except ValueError:
        raise _not_found(NOT_FOUND_MESSAGE) from None
    if not preview_token_is_valid(parsed_id, token):
        raise _not_found(NOT_FOUND_MESSAGE)
    sample = await _get_lab_sample(db, parsed_id)
    playable = sample_playable_file(sample) if sample is not None else None
    if playable is None:
        raise _not_found(NOT_FOUND_MESSAGE)
    path, media_type = playable
    return path, media_type, f"muestra-{parsed_id}.{sample.file_format.lower()}"


# ------------------------------------------------------------------ analysis cache (S3-S5)
#
# Passes per video (decision documented in backend/README.md, "Laboratorio por habilidad"):
# - REFERENCE samples are only ever compared by pose -> pose pass only.
# - TRAINING samples get every pass the *skill* measures (pose if any level replicates a reference,
#   ball if any level has a BALL_TOUCH_STREAK criterion): calibration uses a level's samples as
#   negatives for higher levels and the level estimator mixes similarity to every level reference with
#   the ball streak, so a criterion-less sample of a mixed level gets both passes.
# - A validation video gets the passes of the evaluated levels (target level only, or all levels).


def _level_needs(level: SkillLevel) -> tuple[bool, bool]:
    criteria = level_criteria(level)
    if not criteria:
        return True, False  # implicit REFERENCE_REPLICATION criterion
    return (
        any(item.metric_type == METRIC_REFERENCE_REPLICATION for item in criteria),
        any(item.metric_type == METRIC_BALL_TOUCH_STREAK for item in criteria),
    )


def levels_analysis_needs(levels: list[SkillLevel]) -> tuple[bool, bool]:
    """(need_pose, need_ball) to evaluate every level of ``levels``."""
    need_pose = need_ball = False
    for level in levels:
        pose, ball = _level_needs(level)
        need_pose, need_ball = need_pose or pose, need_ball or ball
    return need_pose, need_ball


def sample_analysis_needs(skill: Skill, sample: DatasetSample) -> tuple[bool, bool]:
    if sample.sample_role == SAMPLE_ROLE_REFERENCE:
        return True, False
    return levels_analysis_needs(list(skill.levels))


def analysis_is_current(analysis: Any, need_pose: bool, need_ball: bool) -> bool:
    """False when the cached analysis is missing, from another engine version or lacks a needed pass."""
    if not isinstance(analysis, dict) or analysis.get("engine_version") != ENGINE_VERSION:
        return False
    if analysis.get("readable") is not True:
        return True  # the file itself cannot be decoded; re-running cannot help
    if need_pose and analysis.get("pose_status") in (POSE_NOT_REQUESTED, POSE_MODEL_UNAVAILABLE):
        return False  # pass never ran, or the pose model was missing and may be installed now
    if need_ball and analysis.get("ball_status") == BALL_NOT_REQUESTED:
        return False
    return True


def _passes_to_run(analysis: Any, need_pose: bool, need_ball: bool) -> tuple[bool, bool]:
    """Needed passes plus the ones the cached analysis already has (a recompute never loses a pass)."""
    current = isinstance(analysis, dict) and analysis.get("engine_version") == ENGINE_VERSION
    return (
        need_pose or (current and analysis.get("pose_status") == POSE_OK),
        need_ball or (current and analysis.get("ball_status") == BALL_OK),
    )


async def _run_analysis(video_path: Path | str, need_pose: bool, need_ball: bool) -> dict[str, Any]:
    """CPU-bound engine call off the event loop (the engine never raises)."""
    return await asyncio.to_thread(analyze_video, str(video_path), need_pose=need_pose, need_ball=need_ball)


async def ensure_sample_analyses(db: AsyncSession, skill: Skill, samples: list[DatasetSample]) -> int:
    """(Re)compute missing/stale analyses of ``samples`` and persist them; returns how many were computed."""
    computed = 0
    for sample in samples:
        need_pose, need_ball = sample_analysis_needs(skill, sample)
        if analysis_is_current(sample.analysis, need_pose, need_ball):
            continue
        need_pose, need_ball = _passes_to_run(sample.analysis, need_pose, need_ball)
        try:
            analysis = await _run_analysis(sample_local_path(sample), need_pose, need_ball)
        except Exception:  # noqa: BLE001 - keep the previous cache; the engine itself never raises
            logger.exception("Could not analyze lab sample %s", sample.id)
            continue
        sample.analysis = analysis
        computed += 1
    if computed:
        await db.commit()
    return computed


# ------------------------------------------------------------------ engine specification (S5, S6)


async def _skill_references(db: AsyncSession, skill: Skill) -> dict[tuple, DatasetSample]:
    """Current reference per (level id, criterion key | None) of the skill's existing levels/criteria."""
    valid: set[tuple] = set()
    for level in skill.levels:
        valid.add((level.id, None))
        valid.update((level.id, item.key) for item in level_criteria(level))
    references: dict[tuple, DatasetSample] = {}
    for sample in await list_skill_samples(db, skill.id, role=SAMPLE_ROLE_REFERENCE):
        key = (sample.skill_level_id, sample.criterion_key)
        if key in valid:
            references.setdefault(key, sample)  # newest first
    return references


async def build_skill_spec(db: AsyncSession, skill: Skill) -> SkillSpec:
    """Engine `SkillSpec` from the catalog skill and the cached analyses of its reference videos."""
    references = await _skill_references(db, skill)

    def analysis_of(level_id: uuid.UUID, criterion_key: Optional[str]) -> Optional[dict]:
        sample = references.get((level_id, criterion_key))
        return sample.analysis if sample is not None and isinstance(sample.analysis, dict) else None

    levels = []
    for level in sorted(skill.levels, key=lambda item: item.level_number):
        criteria = level_criteria(level)
        criterion_references = {
            item.key: analysis_of(level.id, item.key)
            for item in criteria
            if analysis_of(level.id, item.key) is not None
        }
        levels.append(LevelSpec(
            level_id=str(level.id),
            level_number=level.level_number,
            name=level.name,
            min_score=level_min_score(level),
            criteria=tuple(
                CriterionSpec(key=item.key, name=item.name, weight=float(item.weight),
                              metric_type=item.metric_type, target=item.target)
                for item in criteria
            ),
            reference=analysis_of(level.id, None),
            criterion_references=criterion_references,
        ))
    return SkillSpec(
        skill_id=str(skill.id),
        name=skill.name,
        min_approval_threshold=float(skill.min_approval_threshold or 0.0),
        levels=tuple(levels),
    )


async def _prepare_spec(db: AsyncSession, skill: Skill) -> SkillSpec:
    references = await _skill_references(db, skill)
    await ensure_sample_analyses(db, skill, list(references.values()))
    return await build_skill_spec(db, skill)


# ------------------------------------------------------------------ train (S5)


async def _next_version(db: AsyncSession, skill_id: uuid.UUID) -> str:
    versions = (await db.execute(
        select(ModelVersion.version).where(
            ModelVersion.skill_id == skill_id, ModelVersion.nombre == SKILL_VALIDATOR_MODEL_NAME
        )
    )).scalars().all()
    numbers = [int(match.group(1)) for value in versions if (match := re.fullmatch(r"v(\d+)", value or ""))]
    return f"v{max(numbers, default=0) + 1}"


async def train_skill_validator(db: AsyncSession, skill_id: uuid.UUID) -> ModelVersion:
    """Few-shot calibration from the labeled TRAINING videos -> new active `skill_validator` version."""
    skill = await load_skill_for_lab(db, skill_id)
    spec = await _prepare_spec(db, skill)
    level_ids = {level.id for level in skill.levels}
    training = [
        sample for sample in reversed(await list_skill_samples(db, skill.id, role=SAMPLE_ROLE_TRAINING))
        if sample.skill_level_id in level_ids
    ]
    await ensure_sample_analyses(db, skill, training)
    labeled = [
        LabeledSample(
            level_id=str(sample.skill_level_id),
            criterion_key=sample.criterion_key,
            analysis=sample.analysis if isinstance(sample.analysis, dict) else {},
        )
        for sample in training
    ]
    outcome = await asyncio.to_thread(calibrate_skill, spec, labeled)
    version = await _next_version(db, skill.id)
    samples_per_level = {
        str(level.id): sum(1 for sample in training if sample.skill_level_id == level.id)
        for level in sorted(skill.levels, key=lambda item: item.level_number)
    }
    metrics = {
        **(outcome.get("metrics") or {}),
        "samples_per_level": samples_per_level,
        "notes": [str(note) for note in outcome.get("notes") or []],
        "engine_version": ENGINE_VERSION,
        CALIBRATION_METRICS_KEY: {**(outcome.get("calibration") or {}), "model_version": version},
    }
    # Deactivate first, in the same transaction (partial unique index uq_model_versions_active_skill).
    await db.execute(
        update(ModelVersion)
        .where(
            ModelVersion.skill_id == skill.id,
            ModelVersion.nombre == SKILL_VALIDATOR_MODEL_NAME,
            ModelVersion.activa.is_(True),
        )
        .values(activa=False)
    )
    model = ModelVersion(
        nombre=SKILL_VALIDATOR_MODEL_NAME,
        version=version,
        ruta_onnx=CALIBRATION_STORAGE_REF,
        metricas=metrics,
        activa=True,
        skill_id=skill.id,
    )
    db.add(model)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise SkillMatchException(
            statuscode=409,
            message="Otro entrenamiento de esta habilidad terminó al mismo tiempo; vuelve a intentarlo.",
        )
    await db.refresh(model)
    return model


def _calibration_of(model: Optional[ModelVersion]) -> Optional[dict[str, Any]]:
    if model is None:
        return None
    stored = (model.metricas or {}).get(CALIBRATION_METRICS_KEY)
    return {**(stored if isinstance(stored, dict) else {}), "model_version": model.version}


# ------------------------------------------------------------------ validate (S6)


def _unanalyzed(note: str) -> dict[str, Any]:
    """Engine-shaped analysis of a video that was not (or could not be) analyzed."""
    return {
        "engine_version": ENGINE_VERSION,
        "readable": False,
        "duration_seconds": 0.0,
        "frames_analyzed": 0,
        "pose": None,
        "pose_status": POSE_UNREADABLE,
        "ball": None,
        "ball_status": BALL_NOT_REQUESTED,
        "notes": [note],
    }


async def _evaluate(
    db: AsyncSession, skill: Skill, target: Optional[SkillLevel], video_path: Optional[Path | str],
    failure_note: Optional[str] = None,
) -> dict[str, Any]:
    spec = await _prepare_spec(db, skill)
    calibration = _calibration_of(await get_active_skill_model(db, skill.id))
    if failure_note is None:
        need_pose, need_ball = levels_analysis_needs([target] if target is not None else list(skill.levels))
        try:
            analysis = await _run_analysis(video_path, need_pose, need_ball)
        except Exception:  # noqa: BLE001 - the engine never raises; this guards the thread hand-off
            logger.exception("Skill validation analysis failed")
            failure_note = NOTE_ANALYSIS_FAILED
    if failure_note is not None:
        analysis = _unanalyzed(failure_note)
    target_id = str(target.id) if target is not None else None
    result = await asyncio.to_thread(evaluate_skill, spec, analysis, calibration, target_id)
    if failure_note is not None:
        # The specific reason replaces the engine's generic "unreadable video" note.
        result["notes"] = [note for note in result.get("notes", []) if note != NOTE_UNREADABLE]
    return result


async def validate_skill_video(
    db: AsyncSession,
    skill_id: uuid.UUID,
    video_path: Path | str,
    target_level_id: Optional[uuid.UUID] = None,
) -> dict[str, Any]:
    """Public entry point of the validation engine (admin lab today, member flow later).

    Evaluates ``video_path`` against the catalog configuration of the skill, its reference videos and
    the active `skill_validator` calibration (defaults when never trained) and returns the Validation
    result of the contract. Never raises because of the video (unreadable/missing file -> score 0,
    ``analysis_complete: false``). An unknown skill (404 «Habilidad no encontrada») or a target level of
    another skill (404 «Nivel no encontrado para esta habilidad.») raise ``SkillMatchException``.
    Persists nothing about the video; it may refresh the cached analyses of the skill's reference videos.
    """
    skill = await load_skill_for_lab(db, skill_id)
    target = _find_level(skill, target_level_id) if target_level_id is not None else None
    return await _evaluate(db, skill, target, video_path)


def _validation_suffix(filename: Optional[str]) -> str:
    suffix = Path(filename or "").suffix.lower()
    return suffix if suffix in _VALIDATE_ALLOWED_SUFFIXES else ".mp4"


async def _spool_upload(upload: UploadFile, target: Path) -> Optional[int]:
    """Copy the upload to ``target``; its size, or None when it exceeds the lab cap."""
    size = 0
    with target.open("wb") as output:
        while chunk := await upload.read(_CHUNK_SIZE):
            size += len(chunk)
            if size > SKILL_LAB_MAX_FILE_SIZE_BYTES:
                return None
            output.write(chunk)
    return size


async def validate_uploaded_video(
    db: AsyncSession,
    skill_id: uuid.UUID,
    upload: Optional[UploadFile],
    target_level_id: Optional[uuid.UUID] = None,
) -> dict[str, Any]:
    """Admin `/validate`: temp copy (200 MB cap) -> same rules as `validate_skill_video`; copy always deleted."""
    skill = await load_skill_for_lab(db, skill_id)
    target = _find_level(skill, target_level_id) if target_level_id is not None else None
    if upload is None:
        return await _evaluate(db, skill, target, None, NOTE_NO_FILE)
    fd, temp_name = tempfile.mkstemp(prefix="skillmatch-skill-validate-", suffix=_validation_suffix(upload.filename))
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        try:
            size = await _spool_upload(upload, temp_path)
        except Exception:  # noqa: BLE001 - interrupted/broken upload stream
            logger.exception("Could not receive the skill validation video")
            size = -1
        if size is None:
            return await _evaluate(db, skill, target, None, NOTE_OVERSIZE)
        if size == 0:
            return await _evaluate(db, skill, target, None, NOTE_EMPTY_FILE)
        if size < 0:
            return await _evaluate(db, skill, target, None, NOTE_RECEIVE_FAILED)
        return await _evaluate(db, skill, target, temp_path)
    finally:
        temp_path.unlink(missing_ok=True)
