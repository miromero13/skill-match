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
from app.main import create_application
from app.models.user import User, UserRole


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
async def test_generate_synthetic_football_dataset_endpoint(
    training_api: dict[str, Any],
):
    client: AsyncClient = training_api["client"]
    admin_headers: dict[str, str] = training_api["admin_headers"]

    res = await client.post(
        "/api/football/training/generate-synthetic",
        headers=admin_headers,
        json={"count": 4, "train_ratio": 0.70, "val_ratio": 0.15},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["statuscode"] == 201
    data = body["data"]
    assert data["generated_count"] == 4
    assert len(data["samples"]) == 4
    assert "train" in data["splits_summary"]
    for sample in data["samples"]:
        assert sample["sample_id"].startswith("SYN-FB-")
        assert sample["storage_path"]
        assert sample["manual_touch_count"] > 0


@pytest.mark.asyncio
async def test_train_model_list_and_activate_lifecycle(
    training_api: dict[str, Any],
):
    client: AsyncClient = training_api["client"]
    admin_headers: dict[str, str] = training_api["admin_headers"]

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

    model_id = model_data["id"]

    # 2. List models
    list_res = await client.get(
        "/api/football/training/models",
        headers=admin_headers,
    )
    assert list_res.status_code == 200
    models_list = list_res.json()["data"]
    assert any(m["id"] == model_id and m["activa"] is True for m in models_list)

    # 3. Train second inactive model
    train2_res = await client.post(
        "/api/football/training/train",
        headers=admin_headers,
        json={"version_tag": "2.1.0-inactive", "activate": False},
    )
    assert train2_res.status_code == 200
    model2_id = train2_res.json()["data"]["id"]
    assert train2_res.json()["data"]["activa"] is False

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
