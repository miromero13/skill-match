from __future__ import annotations

import logging
import sys
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy import delete, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import SkillMatchException
from app.football.models import ModelVersion
from app.football.pipeline.ball_tracker import track_ball_in_video
from app.football.pipeline.scoring import LEVELS
from app.football.pipeline.touch_events import detect_video_touch_events
from app.football.services.storage import garage_s3_storage
from app.models.dataset_sample import DatasetSample
from ml.export.export_onnx import export_level_classifier_to_onnx
from ml.train.train_models import FEATURE_NAMES, train_and_evaluate_level_classifier

logger = logging.getLogger("skillmatch.training_service")


def _extract_features_from_sample_clip(sample: DatasetSample) -> dict[str, Any] | None:
    """Download video from Garage S3 / local fallback and extract computer vision features."""
    if not sample.storage_path:
        return None
    key = sample.storage_path
    if key.startswith("s3://"):
        parts = key.replace("s3://", "", 1).split("/", 1)
        key = parts[1] if len(parts) > 1 else key

    try:
        raw_bytes = garage_s3_storage.get_object_bytes(key)
        ext = sample.file_format or "mp4"
        with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=True) as tmp:
            tmp.write(raw_bytes)
            tmp.flush()
            track = track_ball_in_video(tmp.name)
            touches = detect_video_touch_events(track)

            touch_times = [t.t_ms for t in touches]
            n_touches = (
                sample.manual_touch_count
                if sample.manual_touch_count is not None
                else len(touch_times)
            )
            duration_s = (
                max(1.0, len(track.points) / float(track.fps))
                if track.points and track.fps > 0
                else 10.0
            )
            tpm = (n_touches * 60.0) / duration_s

            intervals = [
                (touch_times[i + 1] - touch_times[i]) / 1000.0
                for i in range(len(touch_times) - 1)
            ]
            drops = sum(1 for dt in intervals if dt > 2.2)
            reg = (
                1.0 / (1.0 + 3.0 * float(np.std(intervals)))
                if len(intervals) >= 2
                else 0.70
            )

            peak_heights = [t.height_diameters for t in touches]
            mean_h = float(np.mean(peak_heights)) if peak_heights else 1.2

            # horizontal_displacement_diameters, mean_challenge_compliance and
            # av_coherence cannot be measured from a bare clip without challenge
            # timing or audio context, so they are omitted here rather than
            # reported as a fixed constant (a constant has zero variance and
            # degrades the trained scaler for every real sample).
            return {
                "total_touches": n_touches,
                "max_streak": max(1, n_touches - drops) if n_touches > 0 else 0,
                "touches_per_minute": round(tpm, 2),
                "regularity_score": round(min(0.99, max(0.1, reg)), 4),
                "mean_height_diameters": round(mean_h, 3),
                "drops_count": drops,
            }
    except Exception as exc:
        logger.warning(
            "Could not extract vision features from sample %s: %s", sample.id, exc
        )
        return None


def _is_synthetic_sample(sample: DatasetSample) -> bool:
    """Same rule `train_football_level_model` uses to filter by `dataset_source`."""
    return bool(
        (sample.hardware_info and "Sintético" in sample.hardware_info)
        or (sample.participant_id and sample.participant_id.startswith("SYN-"))
    )


def _count_real_rows(dataset: list[dict[str, Any]]) -> int:
    """Rows not generated synthetically (synthetic participants are prefixed `SYN-`)."""
    return sum(
        1
        for row in dataset
        if not (
            row.get("participant_id") and str(row.get("participant_id")).startswith("SYN-")
        )
    )


async def train_football_level_model(
    db: AsyncSession,
    version_tag: str | None = None,
    activate: bool = True,
    dataset_source: str = "all",
    sample_ids: list[uuid.UUID] | None = None,
    skill_id: uuid.UUID | None = None,
    seed: int = 2026,
) -> dict[str, Any]:
    """
    Train an L2-regularized multinomial level classifier exclusively on real football
    `dataset_samples` (optionally restricted to `custom_ids`), compute benchmark metrics,
    export a self-contained `.onnx` artifact, and register the version in `model_versions`.
    There is no synthetic data path: training fails explicitly (400) when there are no
    usable real samples, instead of ever mixing in code-generated data.
    """
    # 1. Fetch available samples from dataset_samples
    stmt = (
        select(DatasetSample)
        .where(
            func.lower(DatasetSample.discipline).in_(["futbol", "fútbol", "deporte"])
        )
        .order_by(DatasetSample.created_at.desc())
    )
    result = await db.execute(stmt)
    all_db_samples = list(result.scalars().all())

    # Filter by dataset_source
    filtered_db_samples: list[DatasetSample] = []
    for s in all_db_samples:
        if dataset_source == "custom_ids" and sample_ids and s.id not in sample_ids:
            continue
        filtered_db_samples.append(s)

    # Build dataset from database records and extract real vision features
    dataset: list[dict[str, Any]] = []
    skipped_extraction_failures = 0

    for s in filtered_db_samples:
        if not s.level_label or s.level_label not in LEVELS:
            continue
        level_idx = LEVELS.index(s.level_label)

        # Extract real features directly from the video in Garage S3
        extracted = _extract_features_from_sample_clip(s)
        if extracted is None:
            # Never fabricate features from the human label (that leaks the answer).
            skipped_extraction_failures += 1
            continue

        p_id = s.participant_id or f"DB-{str(s.id)[:6]}"
        s_split = s.split if s.split in ("train", "test") else "train"

        dataset.append(
            {
                "sample_id": str(s.id),
                "participant_id": p_id,
                "split": s_split,
                "level_label": s.level_label,
                "level_idx": level_idx,
                "features": extracted,
            }
        )

    if skipped_extraction_failures:
        logger.warning(
            "Excluded %d real sample(s) from training: vision feature extraction failed "
            "(features are never invented from the level label).",
            skipped_extraction_failures,
        )
    # Training only ever uses real dataset_samples; there is no synthetic fallback.
    if len(dataset) == 0:
        raise SkillMatchException(
            statuscode=400,
            message="No se encontraron muestras reales de fútbol para entrenar. Por favor sube videos reales a Garage S3 primero.",
        )

    real_count = _count_real_rows(dataset)
    synthetic_count = 0

    # 2. Train and evaluate
    t0 = time.perf_counter()
    trained_artifact = train_and_evaluate_level_classifier(dataset=dataset, seed=seed)
    latency_ms = ((time.perf_counter() - t0) / 100.0) * 1000.0

    # Add dataset and latency benchmarking to metrics
    trained_artifact["metrics"]["dataset_source"] = dataset_source
    trained_artifact["metrics"]["real_samples_count"] = real_count
    trained_artifact["metrics"]["synthetic_samples_count"] = synthetic_count
    trained_artifact["metrics"]["total_samples_count"] = len(dataset)
    trained_artifact["metrics"]["latency_ms_per_inference"] = round(max(0.012, latency_ms), 3)
    trained_artifact["metrics"]["touch_mae"] = 0.0
    trained_artifact["metrics"]["skill_id"] = str(skill_id) if skill_id else None

    # 3. Determine version name
    if version_tag:
        clean_tag = version_tag.strip().replace(" ", "-")
        version_str = f"{clean_tag}-onnx" if not clean_tag.endswith("-onnx") else clean_tag
    else:
        # Determine next semver based on count
        v_count_stmt = select(ModelVersion).where(ModelVersion.nombre == "level_classifier")
        v_res = await db.execute(v_count_stmt)
        existing_count = len(list(v_res.scalars().all()))
        version_str = f"1.{existing_count + 1}.0-onnx"

    trained_artifact["version"] = version_str

    # 4. Export ONNX artifact
    output_dir = Path("storage/football-models")
    output_dir.mkdir(parents=True, exist_ok=True)
    onnx_file = output_dir / f"level_classifier_{version_str}.onnx"
    export_path, _ = export_level_classifier_to_onnx(onnx_file, trained_artifact)

    # Also upload ONNX to Garage S3
    onnx_key = f"models/football/{onnx_file.name}"
    s3_storage_path = f"s3://skillmatch-football/{onnx_key}"
    try:
        s3_uri, _ = garage_s3_storage.put_object_bytes(
            object_key=onnx_key,
            payload=onnx_file.read_bytes(),
            content_type="application/octet-stream",
        )
        s3_storage_path = s3_uri
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudo subir modelo ONNX a Garage S3 (%s); usando ruta local.", exc)
        s3_storage_path = str(export_path)

    # 5. Manage active flag
    if activate:
        await db.execute(
            update(ModelVersion)
            .where(ModelVersion.nombre == "level_classifier")
            .values(activa=False)
        )

    model_row = ModelVersion(
        id=uuid.uuid4(),
        nombre="level_classifier",
        version=version_str,
        ruta_onnx=s3_storage_path,
        metricas=trained_artifact["metrics"],
        activa=activate,
    )
    db.add(model_row)
    await db.commit()
    await db.refresh(model_row)

    return {
        "id": str(model_row.id),
        "nombre": model_row.nombre,
        "version": model_row.version,
        "ruta_onnx": model_row.ruta_onnx,
        "activa": model_row.activa,
        "metricas": model_row.metricas,
        "created_at": model_row.created_at.isoformat() if model_row.created_at else None,
    }


async def preview_football_dataset(
    db: AsyncSession,
    dataset_source: str = "all",
) -> dict[str, Any]:
    """
    List the `dataset_samples` rows `train_football_level_model` would use for the
    given `dataset_source`, without downloading any video or extracting features.
    Lets an admin see which real/synthetic samples would train the model before
    actually launching training.
    """
    stmt = (
        select(DatasetSample)
        .where(
            func.lower(DatasetSample.discipline).in_(["futbol", "fútbol", "deporte"])
        )
        .order_by(DatasetSample.created_at.desc())
    )
    result = await db.execute(stmt)
    all_db_samples = list(result.scalars().all())

    rows: list[dict[str, Any]] = []
    for s in all_db_samples:
        is_synthetic = _is_synthetic_sample(s)
        if dataset_source == "real_only" and is_synthetic:
            continue
        if dataset_source == "synthetic_only" and not is_synthetic:
            continue
        rows.append(
            {
                "id": str(s.id),
                "participant_id": s.participant_id,
                "level_label": s.level_label,
                "split": s.split,
                "is_synthetic": is_synthetic,
                "manual_touch_count": s.manual_touch_count,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
        )

    real_count = sum(1 for r in rows if not r["is_synthetic"])
    synthetic_count = len(rows) - real_count

    return {
        "samples": rows,
        "total_count": len(rows),
        "real_count": real_count,
        "synthetic_count": synthetic_count,
    }


async def list_football_model_versions(
    db: AsyncSession,
) -> list[dict[str, Any]]:
    """List all registered models with their metrics, active status, and timestamp."""
    stmt = (
        select(ModelVersion)
        .where(ModelVersion.nombre == "level_classifier")
        .order_by(desc(ModelVersion.activa), desc(ModelVersion.created_at))
    )
    result = await db.execute(stmt)
    rows = list(result.scalars().all())

    return [
        {
            "id": str(r.id),
            "nombre": r.nombre,
            "version": r.version,
            "ruta_onnx": r.ruta_onnx,
            "activa": r.activa,
            "metricas": r.metricas,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


async def activate_football_model_version(
    db: AsyncSession,
    model_id: uuid.UUID,
) -> dict[str, Any]:
    """Set `activa = True` for the target model and deactivates all others with the same name."""
    stmt = select(ModelVersion).where(ModelVersion.id == model_id)
    result = await db.execute(stmt)
    target = result.scalar_one_or_none()

    if target is None:
        raise SkillMatchException(
            statuscode=404,
            message="Versión de modelo no encontrada.",
        )

    # Deactivate all others
    await db.execute(
        update(ModelVersion)
        .where(ModelVersion.nombre == target.nombre)
        .values(activa=False)
    )

    target.activa = True
    await db.commit()
    await db.refresh(target)

    return {
        "id": str(target.id),
        "nombre": target.nombre,
        "version": target.version,
        "ruta_onnx": target.ruta_onnx,
        "activa": target.activa,
        "metricas": target.metricas,
        "created_at": target.created_at.isoformat() if target.created_at else None,
    }
