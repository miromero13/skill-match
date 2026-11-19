from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.core.exceptions import SkillMatchException
from app.football.services import training_service
from app.models.dataset_sample import DatasetSample


def _real_sample(suffix: str, level: str) -> DatasetSample:
    return DatasetSample(
        id=uuid.uuid4(),
        discipline="futbol",
        challenge="juggling",
        hardware_info="iPhone 15",
        signed_consent=True,
        file_format="mp4",
        file_size_bytes=1024,
        file_hash_sha256="c" * 64,
        storage_path=f"s3://skillmatch-football/does-not-exist/{suffix}.mp4",
        participant_id=f"REAL-{suffix}",
        level_label=level,
        manual_touch_count=15,
        split="train",
    )


@pytest.fixture
async def no_synthetic_db() -> AsyncGenerator[AsyncSession, None]:
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


@pytest.mark.asyncio
async def test_training_never_fills_with_synthetic_data_regardless_of_source(
    no_synthetic_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    With fewer than 24 real samples, training must reject with 400 instead of
    silently mixing in code-generated synthetic participants. This holds for
    the default dataset_source too, not just real_only.
    """
    broken = _real_sample(uuid.uuid4().hex[:8], "Intermedio")
    no_synthetic_db.add(broken)
    await no_synthetic_db.flush()

    # storage_path points at a non-existent object, so extraction fails and the
    # sample is excluded; zero usable real samples remain.
    monkeypatch.setattr(training_service, "_extract_features_from_sample_clip", lambda _s: None)

    with pytest.raises(SkillMatchException) as exc_info:
        await training_service.train_football_level_model(
            db=no_synthetic_db,
            activate=False,
            sample_ids=[broken.id],
        )
    assert exc_info.value.statuscode == 400


def test_generate_grouped_participant_dataset_is_not_imported_by_training_service() -> None:
    import inspect

    source = inspect.getsource(training_service)
    assert "generate_grouped_participant_dataset" not in source


@pytest.mark.asyncio
async def test_duplicate_participant_id_across_splits_rejects_with_400(
    no_synthetic_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    If uploads reused the same participant_id for different real people split
    across train/test (e.g. every single-file upload defaulted to anon-p01),
    training must reject with a clear 400 naming the leaked participant,
    never crash the worker with a bare AssertionError.
    """
    same_id = "anon-p01"
    train_sample = _real_sample("leak-train", "Principiante")
    train_sample.participant_id = same_id
    train_sample.split = "train"
    test_sample = _real_sample("leak-test", "Principiante")
    test_sample.participant_id = same_id
    test_sample.split = "test"
    no_synthetic_db.add_all([train_sample, test_sample])
    await no_synthetic_db.flush()

    monkeypatch.setattr(
        training_service,
        "_extract_features_from_sample_clip",
        lambda _s: {
            "total_touches": 20,
            "max_streak": 15,
            "touches_per_minute": 50.0,
            "regularity_score": 0.75,
            "mean_height_diameters": 1.6,
            "drops_count": 1,
        },
    )

    with pytest.raises(SkillMatchException) as exc_info:
        await training_service.train_football_level_model(
            db=no_synthetic_db,
            activate=False,
            sample_ids=[train_sample.id, test_sample.id],
        )
    assert exc_info.value.statuscode == 400
    assert same_id in exc_info.value.message
