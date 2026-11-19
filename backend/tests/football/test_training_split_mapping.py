from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.football.services import training_service
from app.models.dataset_sample import DatasetSample

_FEATURES: dict[str, Any] = {
    "total_touches": 20,
    "max_streak": 15,
    "touches_per_minute": 50.0,
    "regularity_score": 0.75,
    "mean_height_diameters": 1.6,
    "drops_count": 1,
}


def _real_sample(suffix: str, level: str, participant_id: str, split: str) -> DatasetSample:
    return DatasetSample(
        id=uuid.uuid4(),
        discipline="futbol",
        challenge="juggling",
        hardware_info="iPhone 15",
        signed_consent=True,
        file_format="mp4",
        file_size_bytes=1024,
        file_hash_sha256="f" * 64,
        storage_path=f"s3://skillmatch-football/split-mapping/{suffix}.mp4",
        participant_id=participant_id,
        level_label=level,
        manual_touch_count=20,
        split=split,
    )


@pytest.fixture
async def split_mapping_db() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(settings.async_database_url, pool_pre_ping=True)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:
            async with AsyncSession(
                bind=connection,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            ) as db:
                yield db
        finally:
            await transaction.rollback()
    await engine.dispose()


@pytest.fixture
def captured_training_datasets(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> list[list[dict[str, Any]]]:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(training_service.garage_s3_storage, "access_key_id", None)
    monkeypatch.setattr(
        training_service, "_extract_features_from_sample_clip", lambda _s: dict(_FEATURES)
    )
    captured: list[list[dict[str, Any]]] = []
    real_train = training_service.train_and_evaluate_level_classifier

    def spy(dataset: list[dict[str, Any]] | None = None, seed: int = 2026) -> dict[str, Any]:
        assert dataset is not None
        captured.append(list(dataset))
        return real_train(dataset=dataset, seed=seed)

    monkeypatch.setattr(training_service, "train_and_evaluate_level_classifier", spy)
    return captured


@pytest.mark.asyncio
async def test_validation_split_sample_is_mapped_to_train_not_silently_lost(
    split_mapping_db: AsyncSession,
    captured_training_datasets: list[list[dict[str, Any]]],
) -> None:
    """
    `DatasetSample.split` has three real values: train, val, test. The trainer
    only understands train/test. A sample uploaded as "val" (Validation) must
    still be used by the trainer as a train row (it has real_count), never
    silently vanish or get misreported as a different split than what the
    admin actually chose when the UI exposed "val" as a first-class option.
    """
    suffix = uuid.uuid4().hex[:6]
    train_sample = _real_sample(f"train-{suffix}", "Intermedio", f"P-TRAIN-{suffix}", "train")
    val_sample = _real_sample(f"val-{suffix}", "Intermedio", f"P-VAL-{suffix}", "val")
    test_sample = _real_sample(f"test-{suffix}", "Intermedio", f"P-TEST-{suffix}", "test")
    split_mapping_db.add_all([train_sample, val_sample, test_sample])
    await split_mapping_db.flush()

    await training_service.train_football_level_model(
        db=split_mapping_db,
        activate=False,
        sample_ids=[train_sample.id, val_sample.id, test_sample.id],
        dataset_source="custom_ids",
    )

    dataset = captured_training_datasets[0]
    rows_by_participant = {row["participant_id"]: row for row in dataset}

    assert rows_by_participant[f"P-TRAIN-{suffix}"]["split"] == "train"
    assert rows_by_participant[f"P-VAL-{suffix}"]["split"] == "train"
    assert rows_by_participant[f"P-TEST-{suffix}"]["split"] == "test"
