from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

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


def _sample(
    participant_id: str,
    level: str,
    hardware_info: str = "iPhone 15",
    split: str = "train",
) -> DatasetSample:
    return DatasetSample(
        id=uuid.uuid4(),
        discipline="futbol",
        challenge="juggling",
        hardware_info=hardware_info,
        signed_consent=True,
        file_format="mp4",
        file_size_bytes=2048,
        file_hash_sha256="b" * 64,
        storage_path=f"s3://skillmatch-football/preview/{participant_id}.mp4",
        participant_id=participant_id,
        level_label=level,
        manual_touch_count=20,
        split=split,
    )


def test_is_synthetic_sample_matches_training_filter_rules() -> None:
    real = _sample("REAL-01", "Intermedio")
    synthetic_by_prefix = _sample("SYN-P-003-C01", "Avanzado")
    synthetic_by_hardware = _sample("WHATEVER-02", "Principiante", hardware_info="Cámara Sintético Generada")

    assert training_service._is_synthetic_sample(real) is False
    assert training_service._is_synthetic_sample(synthetic_by_prefix) is True
    assert training_service._is_synthetic_sample(synthetic_by_hardware) is True


@pytest.fixture
async def preview_db() -> AsyncGenerator[AsyncSession, None]:
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
async def test_dataset_preview_endpoint_lists_real_and_synthetic_counts(
    preview_db: AsyncSession,
) -> None:
    real = _sample("REAL-PREVIEW-01", "Avanzado")
    synthetic = _sample("SYN-P-099-C00", "Experto")
    preview_db.add_all([real, synthetic])
    await preview_db.flush()

    app = create_application()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield preview_db

    app.dependency_overrides[get_db] = override_get_db

    admin = User(
        id=uuid.uuid4(),
        email="admin-preview@skillmatch.test",
        full_name="Admin Preview",
        role=UserRole.ADMIN,
        is_active=True,
    )
    preview_db.add(admin)
    await preview_db.flush()
    token = create_access_token(subject=str(admin.id), role=admin.role.value)

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/football/training/dataset-preview",
                headers={"Authorization": f"Bearer {token}"},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["statuscode"] == 200
    sample_ids = {row["id"] for row in body["data"]["samples"]}
    assert str(real.id) in sample_ids
    assert str(synthetic.id) in sample_ids

    real_row = next(r for r in body["data"]["samples"] if r["id"] == str(real.id))
    synthetic_row = next(r for r in body["data"]["samples"] if r["id"] == str(synthetic.id))
    assert real_row["is_synthetic"] is False
    assert synthetic_row["is_synthetic"] is True
    assert body["data"]["real_count"] >= 1
    assert body["data"]["synthetic_count"] >= 1
