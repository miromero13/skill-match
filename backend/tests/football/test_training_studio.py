from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, Generator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.security import create_access_token
from app.db.session import get_db
from app.football.models import ModelVersion
from app.football.services import training_service
from app.football.tasks import celery_app
from app.main import create_application
from app.models.dataset_sample import DatasetSample
from app.models.user import User, UserRole


def _real_fb_sample(suffix: str, level: str) -> DatasetSample:
    return DatasetSample(
        id=uuid.uuid4(),
        discipline="futbol",
        challenge="juggling",
        hardware_info="iPhone 15",
        signed_consent=True,
        file_format="mp4",
        file_size_bytes=4096,
        file_hash_sha256="d" * 64,
        storage_path=f"s3://skillmatch-football/studio-test/{suffix}.mp4",
        participant_id=f"REAL-STUDIO-{suffix}",
        level_label=level,
        manual_touch_count=20,
        split="train",
    )


_FAKE_REAL_FEATURES: dict[str, Any] = {
    "total_touches": 22,
    "max_streak": 18,
    "touches_per_minute": 55.0,
    "regularity_score": 0.8,
    "mean_height_diameters": 1.5,
    "drops_count": 1,
}


# The Celery task trains in its own DB session/event loop, so it only sees rows that
# are really committed (not the savepoint-bound `training_api["db"]`). Tests that run
# training therefore commit through this NullPool sessionmaker (bound to no event loop)
# and clean up after themselves.
_CommittedSession = async_sessionmaker(
    create_async_engine(settings.async_database_url, poolclass=NullPool),
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture
def eager_celery() -> Generator[None, None, None]:
    """
    Run enqueued tasks inline. `task_eager_propagates` must be False so a failing
    training is stored as FAILURE (readable via the status endpoint) instead of
    raising out of `.delay()` inside the POST handler (the eager outcome is stored
    in the result backend, see `task_store_eager_result` in `app.football.tasks`).
    """
    keys = ("task_always_eager", "task_eager_propagates")
    previous = {k: celery_app.conf[k] for k in keys}
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = False
    yield
    for k, v in previous.items():
        celery_app.conf[k] = v


@pytest.fixture
async def committed_training_env() -> AsyncGenerator[dict[str, Any], None]:
    """
    Snapshots which `level_classifier` versions are active, lets the test register
    committed samples/model ids, and on teardown deletes them and restores the
    previously active versions (training with activate=True flips the shared flag).

    Tests must list this fixture BEFORE `training_api`: teardown runs in reverse, so
    the savepoint transaction (which may hold row locks on `model_versions`) is rolled
    back before this cleanup touches the same rows; otherwise cleanup deadlocks.
    """
    async with _CommittedSession() as db:
        res = await db.execute(
            select(ModelVersion.id).where(ModelVersion.activa.is_(True))
        )
        previously_active = list(res.scalars().all())

    env: dict[str, Any] = {"sample_ids": [], "model_ids": []}
    yield env

    async with _CommittedSession() as db:
        if env["sample_ids"]:
            await db.execute(
                delete(DatasetSample).where(DatasetSample.id.in_(env["sample_ids"]))
            )
        if env["model_ids"]:
            await db.execute(
                delete(ModelVersion).where(ModelVersion.id.in_(env["model_ids"]))
            )
        if previously_active:
            await db.execute(
                update(ModelVersion)
                .where(ModelVersion.id.in_(previously_active))
                .values(activa=True)
            )
        await db.commit()


async def _commit_samples(
    env: dict[str, Any], samples: list[DatasetSample]
) -> None:
    async with _CommittedSession() as db:
        db.add_all(samples)
        await db.commit()
    env["sample_ids"].extend(s.id for s in samples)


async def _enqueue_training(
    client: AsyncClient, headers: dict[str, str], body: dict[str, Any]
) -> dict[str, Any]:
    """POST /train (must be 202 + task_id), then read /train/{task_id}/status."""
    res = await client.post(
        "/api/football/training/train", headers=headers, json=body
    )
    assert res.status_code == 202, res.text
    enqueued = res.json()
    assert enqueued["statuscode"] == 202
    assert enqueued["message"] == "Entrenamiento encolado."
    task_id = enqueued["data"]["task_id"]
    assert task_id

    status_res = await client.get(
        f"/api/football/training/train/{task_id}/status", headers=headers
    )
    assert status_res.status_code == 200, status_res.text
    status_body = status_res.json()
    assert status_body["statuscode"] == 200
    assert status_body["message"] == "Estado del entrenamiento recuperado."
    return status_body["data"]


@pytest.fixture
async def training_api() -> AsyncGenerator[dict[str, Any], None]:
    engine = create_async_engine(settings.async_database_url, pool_pre_ping=True)
    app = create_application()
    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:
            async with AsyncSession(
                bind=connection,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            ) as db:
                suffix = uuid.uuid4().hex[:8]
                admin_user = User(
                    id=uuid.uuid4(),
                    email=f"admin-training-{suffix}@skillmatch.io",
                    full_name="Admin Training Studio",
                    role=UserRole.ADMIN,
                    is_active=True,
                    is_locked=False,
                    hashed_password="hashed_pw_test",
                )
                member_user = User(
                    id=uuid.uuid4(),
                    email=f"member-training-{suffix}@skillmatch.io",
                    full_name="Member Regular",
                    role=UserRole.MEMBER,
                    is_active=True,
                    is_locked=False,
                    hashed_password=None,
                )
                db.add(admin_user)
                db.add(member_user)
                await db.flush()

                async def transaction_db() -> AsyncGenerator[AsyncSession, None]:
                    async with AsyncSession(
                        bind=connection,
                        expire_on_commit=False,
                        join_transaction_mode="create_savepoint",
                    ) as request_db:
                        try:
                            yield request_db
                            await request_db.commit()
                        except Exception:
                            await request_db.rollback()
                            raise

                await db.commit()
                app.dependency_overrides[get_db] = transaction_db

                admin_token = create_access_token(
                    subject=str(admin_user.id),
                    role="ADMIN",
                )
                member_token = create_access_token(
                    subject=str(member_user.id),
                    role="MEMBER",
                )

                transport = ASGITransport(app=app, raise_app_exceptions=False)
                async with AsyncClient(
                    transport=transport, base_url="http://testserver"
                ) as client:
                    yield {
                        "app": app,
                        "client": client,
                        "db": db,
                        "admin_token": admin_token,
                        "member_token": member_token,
                        "admin_headers": {"Authorization": f"Bearer {admin_token}"},
                        "member_headers": {"Authorization": f"Bearer {member_token}"},
                    }
        finally:
            await transaction.rollback()
    await engine.dispose()


@pytest.mark.asyncio
async def test_training_endpoints_security_by_obfuscation_404_for_members(
    training_api: dict[str, Any],
):
    client: AsyncClient = training_api["client"]
    member_headers: dict[str, str] = training_api["member_headers"]

    # Non-admin or anonymous receives 404 (obfuscation)
    res_anon = await client.get("/api/football/training/models")
    assert res_anon.status_code == 404

    res_member = await client.get(
        "/api/football/training/models",
        headers=member_headers,
    )
    assert res_member.status_code == 404


@pytest.mark.asyncio
async def test_train_model_with_no_usable_real_samples_reports_failed_status(
    committed_training_env: dict[str, Any],
    training_api: dict[str, Any],
    eager_celery: None,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Restricted via custom_ids to a single sample whose extraction always fails,
    the enqueued training must end as `failed` (never mixing in synthetic data).
    Enqueueing itself can't be rejected: the POST answers 202 before knowing.
    """
    client: AsyncClient = training_api["client"]
    admin_headers: dict[str, str] = training_api["admin_headers"]

    monkeypatch.setattr(
        training_service, "_extract_features_from_sample_clip", lambda _sample: None
    )

    broken = _real_fb_sample("no-usable-sample", "Intermedio")
    await _commit_samples(committed_training_env, [broken])

    status_data = await _enqueue_training(
        client,
        admin_headers,
        {
            "version_tag": "no-data-test",
            "dataset_source": "custom_ids",
            "sample_ids": [str(broken.id)],
        },
    )
    assert status_data["status"] == "failed"
    assert "No se encontraron muestras reales de fútbol" in status_data["message"]
    assert status_data["result"] is None
    assert status_data["processed"] is None
    assert status_data["total"] is None


@pytest.mark.asyncio
async def test_training_status_for_unknown_task_id_is_queued(
    training_api: dict[str, Any],
):
    client: AsyncClient = training_api["client"]
    admin_headers: dict[str, str] = training_api["admin_headers"]

    res = await client.get(
        f"/api/football/training/train/{uuid.uuid4()}/status",
        headers=admin_headers,
    )
    assert res.status_code == 200
    assert res.json()["data"] == {
        "status": "queued",
        "processed": None,
        "total": None,
        "message": None,
        "result": None,
    }


@pytest.mark.asyncio
async def test_training_enqueue_and_status_are_hidden_from_members_with_404(
    training_api: dict[str, Any],
):
    client: AsyncClient = training_api["client"]
    member_headers: dict[str, str] = training_api["member_headers"]

    res_post = await client.post(
        "/api/football/training/train", headers=member_headers, json={}
    )
    assert res_post.status_code == 404

    res_status = await client.get(
        f"/api/football/training/train/{uuid.uuid4()}/status",
        headers=member_headers,
    )
    assert res_status.status_code == 404

    res_anon = await client.get(
        f"/api/football/training/train/{uuid.uuid4()}/status"
    )
    assert res_anon.status_code == 404


@pytest.mark.asyncio
async def test_train_model_list_and_activate_lifecycle(
    committed_training_env: dict[str, Any],
    training_api: dict[str, Any],
    eager_celery: None,
    monkeypatch: pytest.MonkeyPatch,
):
    client: AsyncClient = training_api["client"]
    admin_headers: dict[str, str] = training_api["admin_headers"]

    monkeypatch.setattr(
        training_service,
        "_extract_features_from_sample_clip",
        lambda _sample: dict(_FAKE_REAL_FEATURES),
    )

    samples = [
        _real_fb_sample(f"lifecycle-{i}", level)
        for i, level in enumerate(
            ["Principiante", "Intermedio", "Avanzado", "Experto"] * 6
        )
    ]
    await _commit_samples(committed_training_env, samples)

    # 1. Train model (enqueue -> status; eager mode already finished)
    # Restricted to this test's own sample_ids via custom_ids: the shared dev DB
    # may hold other real samples from prior runs (or from the admin's manual
    # uploads) whose participant_id/split could legitimately collide across
    # splits and now correctly reject training (see test_train_models_participant_leak.py).
    # This test must stay independent of that unrelated state.
    status_data = await _enqueue_training(
        client,
        admin_headers,
        {
            "version_tag": "2.0.0-test",
            "activate": True,
            "dataset_source": "custom_ids",
            "sample_ids": [str(s.id) for s in samples],
        },
    )
    assert status_data["status"] == "done"
    model_data = status_data["result"]
    committed_training_env["model_ids"].append(uuid.UUID(model_data["id"]))
    assert model_data["version"] == "2.0.0-test-onnx"
    assert model_data["activa"] is True
    metrics = model_data["metricas"]
    assert "trained_exact_accuracy" in metrics
    assert "confusion_matrix" in metrics
    assert len(metrics["confusion_matrix"]) == 4
    assert "loss_history" in metrics
    assert metrics["synthetic_samples_count"] == 0
    assert metrics["real_samples_count"] == len(samples)
    assert metrics["latency_ms_per_inference"] > 0
    assert metrics["total_samples_count"] == metrics["real_samples_count"]

    model_id = model_data["id"]

    # 2. List models
    list_res = await client.get(
        "/api/football/training/models",
        headers=admin_headers,
    )
    assert list_res.status_code == 200
    models_list = list_res.json()["data"]
    assert any(m["id"] == model_id and m["activa"] is True for m in models_list)

    # 3. Train second inactive model restricted to a single sample via custom_ids
    status2_data = await _enqueue_training(
        client,
        admin_headers,
        {
            "version_tag": "2.1.0-inactive",
            "activate": False,
            "dataset_source": "custom_ids",
            "sample_ids": [str(samples[0].id)],
        },
    )
    assert status2_data["status"] == "done"
    model2_data = status2_data["result"]
    model2_id = model2_data["id"]
    committed_training_env["model_ids"].append(uuid.UUID(model2_id))
    assert model2_data["activa"] is False
    assert model2_data["metricas"]["real_samples_count"] == 1

    # 4. Activate second model
    activate_res = await client.post(
        f"/api/football/training/models/{model2_id}/activate",
        headers=admin_headers,
    )
    assert activate_res.status_code == 200
    assert activate_res.json()["data"]["activa"] is True

    # Verify first model is now inactive
    list_after = await client.get(
        "/api/football/training/models",
        headers=admin_headers,
    )
    models_after = list_after.json()["data"]
    m1 = next(m for m in models_after if m["id"] == model_id)
    m2 = next(m for m in models_after if m["id"] == model2_id)
    assert m1["activa"] is False
    assert m2["activa"] is True
