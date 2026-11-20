from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from typing import Any

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.exceptions import SkillMatchException
from app.football.models import ModelVersion
from app.football.services import training_service
from app.football.tasks import celery_app, train_level_model_task
from app.models.dataset_sample import DatasetSample

_FAKE_REAL_FEATURES: dict[str, Any] = {
    "total_touches": 22,
    "max_streak": 18,
    "touches_per_minute": 55.0,
    "regularity_score": 0.8,
    "mean_height_diameters": 1.5,
    "drops_count": 1,
}


# The app-wide pooled engine keeps connections bound to whichever event loop first
# used them; pytest-asyncio gives each test its own loop, so tests use a NullPool
# engine instead.
AsyncSessionLocal = async_sessionmaker(
    create_async_engine(settings.async_database_url, poolclass=NullPool),
    class_=AsyncSession,
    expire_on_commit=False,
)


def _real_fb_sample(suffix: str, level: str) -> DatasetSample:
    return DatasetSample(
        id=uuid.uuid4(),
        discipline="futbol",
        challenge="juggling",
        hardware_info="iPhone 15",
        signed_consent=True,
        file_format="mp4",
        file_size_bytes=4096,
        file_hash_sha256="e" * 64,
        storage_path=f"s3://skillmatch-football/celery-task-test/{suffix}.mp4",
        participant_id=f"REAL-CELERY-{suffix}",
        level_label=level,
        manual_touch_count=20,
        split="train",
    )


@pytest.fixture
async def seeded_samples() -> AsyncGenerator[list[uuid.UUID], None]:
    """
    The Celery task opens its own real DB session (`AsyncSessionLocal`), separate
    from any savepoint the test transaction holds. Rows must be really committed
    for the task to see them, and cleaned up explicitly afterwards.
    """
    async with AsyncSessionLocal() as db:
        samples = [
            _real_fb_sample(f"task-{i}", level)
            for i, level in enumerate(
                ["Principiante", "Intermedio", "Avanzado", "Experto"] * 6
            )
        ]
        db.add_all(samples)
        await db.commit()
        sample_ids = [s.id for s in samples]

    yield sample_ids

    async with AsyncSessionLocal() as db:
        await db.execute(
            delete(DatasetSample).where(DatasetSample.id.in_(sample_ids))
        )
        await db.commit()


@pytest.mark.asyncio
async def test_train_level_model_task_runs_eagerly_and_reports_progress(
    seeded_samples: list[uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
):
    """
    In eager mode, the Celery task must run the real async training end-to-end
    (its own DB session, not the test's) and settle on a final SUCCESS result
    with the same metrics shape that `train_football_level_model` returns
    synchronously.
    """
    monkeypatch.setattr(
        training_service,
        "_extract_features_from_sample_clip",
        lambda _sample: dict(_FAKE_REAL_FEATURES),
    )
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True

    progress_updates: list[dict[str, Any]] = []

    def fake_update_state(*_args: Any, **kwargs: Any) -> None:
        progress_updates.append(kwargs)

    monkeypatch.setattr(train_level_model_task, "update_state", fake_update_state)

    async_result = train_level_model_task.delay(
        version_tag="celery-task-test",
        activate=False,
        dataset_source="custom_ids",
        sample_ids=[str(sid) for sid in seeded_samples],
        skill_id=None,
    )
    result_payload = async_result.get(timeout=30)

    try:
        assert len(progress_updates) == len(seeded_samples)
        assert all(u["state"] == "PROGRESS" and u["task_id"] for u in progress_updates)
        assert [u["meta"]["processed"] for u in progress_updates] == list(
            range(1, len(seeded_samples) + 1)
        )
        assert all(u["meta"]["total"] == len(seeded_samples) for u in progress_updates)
        assert all(u["meta"]["message"] for u in progress_updates)
        assert result_payload["version"] == "celery-task-test-onnx"
        assert result_payload["activa"] is False
        assert result_payload["metricas"]["real_samples_count"] == len(seeded_samples)
        assert result_payload["metricas"]["synthetic_samples_count"] == 0
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(
                delete(ModelVersion).where(ModelVersion.id == uuid.UUID(result_payload["id"]))
            )
            await db.commit()


@pytest.mark.asyncio
async def test_train_level_model_task_propagates_no_usable_samples_error(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        training_service, "_extract_features_from_sample_clip", lambda _sample: None
    )
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True

    broken = _real_fb_sample("broken-task", "Intermedio")

    async with AsyncSessionLocal() as db:
        db.add(broken)
        await db.commit()

    try:
        # task_eager_propagates=True: the task's SkillMatchException surfaces at `.delay()`.
        with pytest.raises(SkillMatchException) as exc_info:
            train_level_model_task.delay(
                version_tag="broken-task-test",
                activate=False,
                dataset_source="custom_ids",
                sample_ids=[str(broken.id)],
                skill_id=None,
            )
        assert exc_info.value.statuscode == 400
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(DatasetSample).where(DatasetSample.id == broken.id))
            await db.commit()
