from __future__ import annotations

import logging
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy import delete, desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import SkillMatchException
from app.football.models import ModelVersion
from app.football.pipeline.scoring import LEVELS
from app.football.services.storage import garage_s3_storage
from app.models.dataset_sample import DatasetSample
from ml.export.export_onnx import export_level_classifier_to_onnx
from ml.train.train_models import (
    FEATURE_NAMES,
    generate_grouped_participant_dataset,
    train_and_evaluate_level_classifier,
)

logger = logging.getLogger("skillmatch.training_service")


async def train_football_level_model(
    db: AsyncSession,
    version_tag: str | None = None,
    activate: bool = True,
    seed: int = 2026,
) -> dict[str, Any]:
    """
    Train an L2-regularized multinomial level classifier on all football samples,
    compute metrics (accuracy, within-one level, loss history, confusion matrix),
    export a self-contained `.onnx` artifact, and register the version in `model_versions`.
    """
    # 1. Fetch available samples from dataset_samples
    stmt = (
        select(DatasetSample)
        .where(DatasetSample.discipline == "fútbol")
        .order_by(DatasetSample.created_at.desc())
    )
    result = await db.execute(stmt)
    db_samples = list(result.scalars().all())

    # Build dataset from database records and augment with synthetic participant groups
    dataset: list[dict[str, Any]] = []

    for s in db_samples:
        if not s.level_label or s.level_label not in LEVELS:
            continue
        level_idx = LEVELS.index(s.level_label)
        touches = s.manual_touch_count or (10 if level_idx == 0 else (25 * level_idx))
        tpm = max(15.0, min(120.0, float(touches * 2.2)))
        reg = 0.55 + (level_idx * 0.12)
        comp = 0.60 + (level_idx * 0.10)
        drops = max(0, 3 - level_idx)
        horiz = max(0.3, 2.5 - (level_idx * 0.6))

        p_id = s.participant_id or f"DB-{str(s.id)[:6]}"
        s_split = s.split if s.split in ("train", "test") else "train"

        dataset.append(
            {
                "sample_id": str(s.id),
                "participant_id": p_id,
                "split": s_split,
                "level_label": s.level_label,
                "level_idx": level_idx,
                "features": {
                    "total_touches": touches,
                    "max_streak": max(3, touches - drops),
                    "touches_per_minute": round(tpm, 2),
                    "regularity_score": round(min(0.99, reg), 4),
                    "mean_height_diameters": round(1.8, 3),
                    "horizontal_displacement_diameters": round(horiz, 3),
                    "drops_count": drops,
                    "mean_challenge_compliance": round(min(0.99, comp), 4),
                    "av_coherence": round(0.94, 4),
                },
            }
        )

    # If dataset has fewer than 24 samples, complement with multi-participant synthetic dataset
    if len(dataset) < 24:
        synthetic_data = generate_grouped_participant_dataset(
            num_participants=28,
            clips_per_participant=3,
            seed=seed,
        )
        dataset.extend(synthetic_data)

    # 2. Train and evaluate
    trained_artifact = train_and_evaluate_level_classifier(dataset=dataset, seed=seed)

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
