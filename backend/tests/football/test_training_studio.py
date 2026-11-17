from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.core.security import create_access_token
from app.db.session import get_db
from app.football.services import training_service
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
async def test_train_model_with_no_usable_real_samples_rejects_with_400(
    training_api: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Restricted via custom_ids to a single sample whose extraction always fails,
    training must reject with 400 instead of ever mixing in synthetic data.
    """
    client: AsyncClient = training_api["client"]
    admin_headers: dict[str, str] = training_api["admin_headers"]
    db: AsyncSession = training_api["db"]

    monkeypatch.setattr(
        training_service, "_extract_features_from_sample_clip", lambda _sample: None
    )

    broken = _real_fb_sample("no-usable-sample", "Intermedio")
    db.add(broken)
    await db.commit()

    res = await client.post(
        "/api/football/training/train",
        headers=admin_headers,
        json={
            "version_tag": "no-data-test",
            "dataset_source": "custom_ids",
            "sample_ids": [str(broken.id)],
        },
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_train_model_list_and_activate_lifecycle(
    training_api: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
):
    client: AsyncClient = training_api["client"]
    admin_headers: dict[str, str] = training_api["admin_headers"]

    monkeypatch.setattr(
        training_service,
        "_extract_features_from_sample_clip",
        lambda _sample: dict(_FAKE_REAL_FEATURES),
    )

    db: AsyncSession = training_api["db"]
    samples = [
        _real_fb_sample(f"lifecycle-{i}", level)
        for i, level in enumerate(
            ["Principiante", "Intermedio", "Avanzado", "Experto"] * 6
        )
    ]
    db.add_all(samples)
    await db.commit()

    # 1. Train model
    train_res = await client.post(
        "/api/football/training/train",
        headers=admin_headers,
        json={"version_tag": "2.0.0-test", "activate": True},
    )
    assert train_res.status_code == 200
    train_body = train_res.json()
    model_data = train_body["data"]
    assert model_data["version"] == "2.0.0-test-onnx"
    assert model_data["activa"] is True
    metrics = model_data["metricas"]
    assert "trained_exact_accuracy" in metrics
    assert "confusion_matrix" in metrics
    assert len(metrics["confusion_matrix"]) == 4
    assert "loss_history" in metrics
    assert metrics["synthetic_samples_count"] == 0
    # The shared dev DB may already hold other real samples from prior runs;
    # training must count at least the ones this test inserted, never invent more.
    assert metrics["real_samples_count"] >= len(samples)
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
    train2_res = await client.post(
        "/api/football/training/train",
        headers=admin_headers,
        json={
            "version_tag": "2.1.0-inactive",
            "activate": False,
            "dataset_source": "custom_ids",
            "sample_ids": [str(samples[0].id)],
        },
    )
    assert train2_res.status_code == 200
    model2_data = train2_res.json()["data"]
    model2_id = model2_data["id"]
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
