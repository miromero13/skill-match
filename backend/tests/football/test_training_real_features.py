from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.football.services import training_service
from app.models.dataset_sample import DatasetSample

REAL_FEATURES: dict[str, Any] = {
    "total_touches": 30,
    "max_streak": 25,
    "touches_per_minute": 60.0,
    "regularity_score": 0.8,
    "mean_height_diameters": 1.5,
    "horizontal_displacement_diameters": 0.8,
    "drops_count": 1,
    "mean_challenge_compliance": 0.85,
    "av_coherence": 0.9,
}


def _real_sample(suffix: str, level: str) -> DatasetSample:
    return DatasetSample(
        id=uuid.uuid4(),
        discipline="futbol",
        challenge="juggling",
        hardware_info="iPhone 15",
        signed_consent=True,
        file_format="mp4",
        file_size_bytes=1024,
        file_hash_sha256="a" * 64,
        storage_path=f"s3://skillmatch-football/does-not-exist/{suffix}.mp4",
        participant_id=f"REAL-{suffix}",
        level_label=level,
        manual_touch_count=30,
        split="train",
    )


@pytest.fixture
async def training_db() -> AsyncGenerator[AsyncSession, None]:
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
    """Capture the dataset handed to the trainer, and keep artifacts out of the repo."""
    monkeypatch.chdir(tmp_path)
    # Force the local storage fallback so tests never wait on the remote S3 endpoint.
    monkeypatch.setattr(training_service.garage_s3_storage, "access_key_id", None)
    captured: list[list[dict[str, Any]]] = []
    real_train = training_service.train_and_evaluate_level_classifier

    def spy(dataset: list[dict[str, Any]] | None = None, seed: int = 2026) -> dict[str, Any]:
        assert dataset is not None
        captured.append(list(dataset))
        return real_train(dataset=dataset, seed=seed)

    monkeypatch.setattr(training_service, "train_and_evaluate_level_classifier", spy)
    return captured


@pytest.mark.asyncio
async def test_failed_extraction_sample_is_excluded_not_invented_from_label(
    training_db: AsyncSession,
    captured_training_datasets: list[list[dict[str, Any]]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    broken = _real_sample(uuid.uuid4().hex[:8], "Experto")
    training_db.add(broken)
    await training_db.flush()

    caplog.set_level(logging.WARNING, logger="skillmatch.training_service")
    result = await training_service.train_football_level_model(
        db=training_db,
        version_tag=f"leak-{uuid.uuid4().hex[:6]}",
        activate=False,
        dataset_source="custom_ids",
        sample_ids=[broken.id],
    )

    assert len(captured_training_datasets) == 1
    trained_ids = {row["sample_id"] for row in captured_training_datasets[0]}
    assert str(broken.id) not in trained_ids
    assert result["metricas"]["real_samples_before_synthetic_fill"] == 0
    assert result["metricas"]["real_samples_count"] == 0
    assert any(
        "excluded" in rec.getMessage().lower() and "1" in rec.getMessage()
        for rec in caplog.records
        if rec.levelno == logging.WARNING
    )


@pytest.mark.asyncio
async def test_successfully_extracted_sample_is_kept_and_counted_before_synthetic_fill(
    training_db: AsyncSession,
    captured_training_datasets: list[list[dict[str, Any]]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    good = _real_sample(uuid.uuid4().hex[:8], "Avanzado")
    broken = _real_sample(uuid.uuid4().hex[:8], "Principiante")
    training_db.add_all([good, broken])
    await training_db.flush()

    def fake_extract(sample: DatasetSample) -> dict[str, Any] | None:
        return dict(REAL_FEATURES) if sample.id == good.id else None

    monkeypatch.setattr(training_service, "_extract_features_from_sample_clip", fake_extract)

    result = await training_service.train_football_level_model(
        db=training_db,
        version_tag=f"keep-{uuid.uuid4().hex[:6]}",
        activate=False,
        dataset_source="custom_ids",
        sample_ids=[good.id, broken.id],
    )

    trained_rows = captured_training_datasets[0]
    trained_ids = {row["sample_id"] for row in trained_rows}
    assert str(good.id) in trained_ids
    assert str(broken.id) not in trained_ids
    kept = next(row for row in trained_rows if row["sample_id"] == str(good.id))
    assert kept["features"] == REAL_FEATURES

    metrics = result["metricas"]
    assert metrics["real_samples_before_synthetic_fill"] == 1
    assert metrics["real_samples_count"] == 1
    assert metrics["synthetic_samples_count"] > 0
    assert metrics["total_samples_count"] == len(trained_rows)


def test_extract_features_from_sample_clip_omits_unmeasured_constants(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    horizontal_displacement_diameters, mean_challenge_compliance and av_coherence
    cannot be measured from a bare juggling clip without challenge/audio context.
    A successful real extraction must omit them rather than report a fixed made-up
    value, since a constant has zero variance and degrades the trained scaler.
    """
    from app.football.pipeline.ball_tracker import BallTrack

    monkeypatch.setattr(
        training_service, "track_ball_in_video", lambda _path: BallTrack(points=[], fps=30.0)
    )
    monkeypatch.setattr(training_service, "detect_video_touch_events", lambda _track: [])
    monkeypatch.setattr(
        training_service.garage_s3_storage,
        "get_object_bytes",
        lambda _key: b"fake-mp4-bytes",
    )

    sample = _real_sample("omit-constants", "Intermedio")
    sample.manual_touch_count = 12

    extracted = training_service._extract_features_from_sample_clip(sample)

    assert extracted is not None
    for unmeasured_key in (
        "horizontal_displacement_diameters",
        "mean_challenge_compliance",
        "av_coherence",
    ):
        assert unmeasured_key not in extracted


@pytest.mark.asyncio
async def test_real_only_with_all_extractions_failed_still_rejects_with_400(
    training_db: AsyncSession,
    captured_training_datasets: list[list[dict[str, Any]]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.exceptions import SkillMatchException

    monkeypatch.setattr(training_service, "_extract_features_from_sample_clip", lambda _s: None)

    broken = _real_sample(uuid.uuid4().hex[:8], "Intermedio")
    training_db.add(broken)
    await training_db.flush()

    with pytest.raises(SkillMatchException) as exc_info:
        await training_service.train_football_level_model(
            db=training_db,
            activate=False,
            dataset_source="real_only",
            sample_ids=[broken.id],
        )
    assert exc_info.value.statuscode == 400
    assert captured_training_datasets == []
