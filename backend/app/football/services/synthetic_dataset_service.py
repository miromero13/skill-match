from __future__ import annotations

import hashlib
import logging
import tempfile
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.football.pipeline.scoring import LEVELS
from app.football.services.storage import garage_s3_storage
from app.models.dataset_sample import DatasetSample
from app.models.user import User
from tests.football.synthetic.generator import (
    SyntheticJugglingSpec,
    generate_synthetic_juggling_clip,
)

logger = logging.getLogger("skillmatch.synthetic_dataset")


async def generate_and_store_synthetic_samples(
    db: AsyncSession,
    admin_user: User,
    count: int = 12,
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
    seed: int = 2026,
) -> dict[str, Any]:
    """
    Generate `count` synthetic football juggling video samples with exact ground-truth
    touches and realistic physics, upload them to Garage S3 (or local storage fallback),
    and register them in the `dataset_samples` database table partitioned into train/val/test splits.
    """
    safe_count = max(1, min(count, 48))
    rng = np.random.default_rng(seed)

    created_samples: list[dict[str, Any]] = []
    splits_summary: dict[str, int] = {"train": 0, "val": 0, "test": 0}
    levels_summary: dict[str, int] = {lvl: 0 for lvl in LEVELS}

    with tempfile.TemporaryDirectory() as tmp_str:
        tmp_dir = Path(tmp_str)

        for idx in range(safe_count):
            sample_uuid = uuid.uuid4()
            sample_id = f"SYN-FB-{sample_uuid.hex[:8].upper()}"
            participant_id = f"SYN-P-{(idx % 12) + 1:03d}"

            # Partition assignment based on participant grouping
            p_num = (idx % 12) + 1
            if p_num <= round(12 * train_ratio):
                split = "train"
            elif p_num <= round(12 * (train_ratio + val_ratio)):
                split = "val"
            else:
                split = "test"

            level_idx = idx % len(LEVELS)
            level_label = LEVELS[level_idx]

            # Level parameters
            if level_idx == 0:  # Principiante
                num_touches = int(rng.integers(4, 9))
                duration_s = float(num_touches * 0.95 + 1.2)
                intervals_ms = [int(rng.integers(850, 1100)) for _ in range(num_touches - 1)]
                noise_std = 3.5
                peak_height = 1.4
            elif level_idx == 1:  # Intermedio
                num_touches = int(rng.integers(10, 19))
                duration_s = float(num_touches * 0.75 + 1.0)
                intervals_ms = [int(rng.integers(680, 850)) for _ in range(num_touches - 1)]
                noise_std = 2.0
                peak_height = 2.0
            elif level_idx == 2:  # Avanzado
                num_touches = int(rng.integers(22, 38))
                duration_s = float(num_touches * 0.58 + 0.8)
                intervals_ms = [int(rng.integers(500, 680)) for _ in range(num_touches - 1)]
                noise_std = 1.2
                peak_height = 2.5
            else:  # Experto
                num_touches = int(rng.integers(42, 65))
                duration_s = float(num_touches * 0.45 + 0.6)
                intervals_ms = [int(rng.integers(400, 520)) for _ in range(num_touches - 1)]
                noise_std = 0.8
                peak_height = 2.8

            # Calculate cumulative touch times
            touch_times: list[int] = [600]
            current_t = 600
            for interval in intervals_ms:
                current_t += interval
                touch_times.append(current_t)

            spec = SyntheticJugglingSpec(
                duration_s=min(duration_s, 20.0),
                fps=30,
                width=640,
                height=360,
                ball_radius_px=22,
                touch_times_ms=touch_times,
                peak_height_diameters=peak_height,
                background_noise_std=noise_std,
                seed=int(rng.integers(10, 99999)),
            )

            clip_res = generate_synthetic_juggling_clip(
                output_dir=tmp_dir,
                spec=spec,
                clip_name=f"clip_{sample_uuid.hex}",
                include_audio=True,
            )

            video_bytes = clip_res.video_path.read_bytes()
            sha256_hash = hashlib.sha256(video_bytes).hexdigest()
            file_size = len(video_bytes)

            object_key = f"datasets/futbol/{sample_id}.mp4"
            storage_path = f"s3://skillmatch-football/{object_key}"

            # Attempt upload to Garage S3
            try:
                s3_uri, _ = garage_s3_storage.put_object_bytes(
                    object_key=object_key,
                    payload=video_bytes,
                    content_type="video/mp4",
                )
                storage_path = s3_uri
            except Exception as exc:  # noqa: BLE001
                logger.warning("Garage S3 upload fallback for %s: %s", sample_id, exc)
                # Local storage fallback
                local_dir = Path("storage") / "datasets" / "futbol"
                local_dir.mkdir(parents=True, exist_ok=True)
                (local_dir / f"{sample_id}.mp4").write_bytes(video_bytes)
                storage_path = f"datasets/futbol/{sample_id}.mp4"

            surface = str(rng.choice(["pasto", "cemento", "parquet"]))
            noise_level = "alto" if noise_std >= 3.0 else ("medio" if noise_std >= 1.5 else "bajo")

            sample_model = DatasetSample(
                id=sample_uuid,
                discipline="fútbol",
                challenge="dominadas",
                hardware_info="Simulador Sintético de Dominadas (Física y Visión 4D)",
                signed_consent=True,
                file_format="mp4",
                file_size_bytes=file_size,
                file_hash_sha256=sha256_hash,
                storage_path=storage_path,
                uploaded_by_id=admin_user.id,
                participant_id=participant_id,
                level_label=level_label,
                manual_touch_count=len(clip_res.ground_truth_touch_ms),
                noise_level=noise_level,
                surface=surface,
                split=split,
            )
            db.add(sample_model)

            splits_summary[split] = splits_summary.get(split, 0) + 1
            levels_summary[level_label] = levels_summary.get(level_label, 0) + 1

            created_samples.append(
                {
                    "id": str(sample_uuid),
                    "sample_id": sample_id,
                    "participant_id": participant_id,
                    "level_label": level_label,
                    "manual_touch_count": len(clip_res.ground_truth_touch_ms),
                    "split": split,
                    "storage_path": storage_path,
                    "file_size_bytes": file_size,
                    "duration_s": round(spec.duration_s, 2),
                }
            )

        await db.commit()

    return {
        "generated_count": len(created_samples),
        "splits_summary": splits_summary,
        "levels_summary": levels_summary,
        "samples": created_samples,
    }
