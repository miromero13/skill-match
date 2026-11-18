from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.core.security import create_access_token
from app.db.session import get_db
from app.football.services.storage import GarageS3StorageService
from app.football.tasks import celery_app
from app.main import create_application
from app.models.user import User, UserRole


@pytest.fixture
async def football_phase1_api() -> AsyncGenerator[dict[str, Any], None]:
    celery_app.conf.task_always_eager = True
    engine = create_async_engine(settings.async_database_url, pool_pre_ping=True)
    app = create_application()
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                async with AsyncSession(
                    bind=connection,
                    expire_on_commit=False,
                    join_transaction_mode="create_savepoint",
                ) as db:
                    suffix = uuid.uuid4().hex[:8]
                    member_user = User(
                        id=uuid.uuid4(),
                        email=f"football-p1-{suffix}@skillmatch.io",
                        full_name="Jugador Prueba Fase 1",
                        role=UserRole.MEMBER,
                        is_active=True,
                        is_locked=False,
                        hashed_password=None,
                    )
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
                            "member_token": member_token,
                            "member_user": member_user,
                            "db": db,
                        }
                    app.dependency_overrides.clear()
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_session_state_transitions_env_liveness_calibration(
    football_phase1_api: dict[str, Any],
) -> None:
    client: AsyncClient = football_phase1_api["client"]
    token: str = football_phase1_api["member_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create session (estado: created)
    create_resp = await client.post("/api/v1/football/sessions", headers=headers, json={})
    assert create_resp.status_code == 201
    session_id = create_resp.json()["data"]["session_id"]

    # 2. Failed env-check (low brightness, no ball) keeps state `created` and reports failures
    bad_env = await client.post(
        f"/api/v1/football/sessions/{session_id}/env-check",
        headers=headers,
        json={
            "brightness": 15.0,
            "noise_db": 45.0,
            "face_detected": True,
            "ball_detected": False,
            "latency_ms": 40.0,
        },
    )
    assert bad_env.status_code == 200
    bad_data = bad_env.json()["data"]
    assert bad_data["passed"] is False
    assert bad_data["estado"] == "created"
    assert len(bad_data["failures"]) == 2

    # 3. Passing env-check transitions to `env_check`
    ok_env = await client.post(
        f"/api/v1/football/sessions/{session_id}/env-check",
        headers=headers,
        json={
            "brightness": 120.0,
            "noise_db": 45.0,
            "face_detected": True,
            "ball_detected": True,
            "latency_ms": 40.0,
        },
    )
    assert ok_env.status_code == 200
    assert ok_env.json()["data"]["passed"] is True
    assert ok_env.json()["data"]["estado"] == "env_check"

    # 4. Passing liveness transitions to `liveness`
    live_resp = await client.post(
        f"/api/v1/football/sessions/{session_id}/liveness",
        headers=headers,
        json={"challenge_passed": True, "gesture_code": "turn_left", "confidence": 0.96},
    )
    assert live_resp.status_code == 200
    assert live_resp.json()["data"]["estado"] == "liveness"

    # 5. Calibration touch transitions to `recording`
    cal_resp = await client.post(
        f"/api/v1/football/sessions/{session_id}/calibration",
        headers=headers,
        json={"client_touch_timestamp_ms": 1850, "estimated_ball_radius_px": 34.5},
    )
    assert cal_resp.status_code == 200
    assert cal_resp.json()["data"]["estado"] == "recording"


@pytest.mark.asyncio
async def test_40s_chunked_upload_resume_and_garage_s3_assembly(
    football_phase1_api: dict[str, Any],
) -> None:
    """
    Phase 1 'Hecho cuando':
    Un video de 40 s (8 fragmentos de 5 s) se sube por fragmentos, se reanuda tras
    cortar la red (reintento idempotente) y queda ensamblado en Garage S3 con su hash.
    """
    client: AsyncClient = football_phase1_api["client"]
    token: str = football_phase1_api["member_token"]
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = await client.post("/api/v1/football/sessions", headers=headers, json={})
    assert create_resp.status_code == 201
    session_id = create_resp.json()["data"]["session_id"]

    # Prepare 8 synthetic 5-second video chunks (total 40s)
    chunks: list[bytes] = [
        f"FOOTBALL-40S-SYNTHETIC-CHUNK-{idx:02d}-".encode() + (bytes([idx]) * 2048)
        for idx in range(8)
    ]
    expected_full_bytes = b"".join(chunks)
    expected_full_sha256 = hashlib.sha256(expected_full_bytes).hexdigest()

    # Step 1: Upload chunks 0..3 before simulated network cut
    for idx in range(4):
        chunk_sha = hashlib.sha256(chunks[idx]).hexdigest()
        res = await client.put(
            f"/api/v1/football/sessions/{session_id}/chunks/{idx}",
            headers={
                **headers,
                "Content-Type": "video/mp4",
                "X-Chunk-Sha256": chunk_sha,
            },
            content=chunks[idx],
        )
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["chunk_index"] == idx
        assert data["sha256"] == chunk_sha
        assert data["idempotent_replay"] is False
        assert data["estado"] == "uploading"

    # Attempt finalize prematurely (missing chunks 4..7) -> must fail with 400
    early_fin = await client.post(
        f"/api/v1/football/sessions/{session_id}/finalize",
        headers=headers,
        json={"expected_chunks": 8, "duration_seconds": 40.0},
    )
    assert early_fin.status_code == 400
    assert "faltan" in early_fin.json()["message"].lower()

    # Step 2: Client queries session status after network cut to discover confirmed chunks
    status_resp = await client.get(
        f"/api/v1/football/sessions/{session_id}",
        headers=headers,
    )
    assert status_resp.status_code == 200
    confirmed = status_resp.json()["data"]["confirmed_chunks"]
    assert confirmed == [0, 1, 2, 3]

    # Step 3: Client replays chunk 3 (idempotent check) and uploads remaining chunks 4..7
    replay_sha = hashlib.sha256(chunks[3]).hexdigest()
    replay_res = await client.put(
        f"/api/v1/football/sessions/{session_id}/chunks/{3}",
        headers={
            **headers,
            "Content-Type": "video/mp4",
            "X-Chunk-Sha256": replay_sha,
        },
        content=chunks[3],
    )
    assert replay_res.status_code == 200
    assert replay_res.json()["data"]["idempotent_replay"] is True

    for idx in range(4, 8):
        chunk_sha = hashlib.sha256(chunks[idx]).hexdigest()
        res = await client.put(
            f"/api/v1/football/sessions/{session_id}/chunks/{idx}",
            headers={
                **headers,
                "Content-Type": "video/mp4",
                "X-Chunk-Sha256": chunk_sha,
            },
            content=chunks[idx],
        )
        assert res.status_code == 200
        assert res.json()["data"]["idempotent_replay"] is False

    # Step 4: Finalize session -> 202 Accepted, assembled in Garage S3 with exact SHA-256
    fin_resp = await client.post(
        f"/api/v1/football/sessions/{session_id}/finalize",
        headers=headers,
        json={"expected_chunks": 8, "duration_seconds": 40.0, "fps": 30.0},
    )
    assert fin_resp.status_code == 202
    fin_data = fin_resp.json()["data"]
    assert fin_data["estado"] == "processing"
    assert fin_data["total_chunks"] == 8
    assert fin_data["assembled_size_bytes"] == len(expected_full_bytes)
    assert fin_data["assembled_sha256"] == expected_full_sha256
    assert fin_data["assembled_uri"].endswith(
        f"sessions/{session_id}/assembled/recording.mp4"
    )

    # Verify assembled object exists in Garage S3 / storage and matches exact bytes
    storage = GarageS3StorageService()
    assembled_key = f"sessions/{session_id}/assembled/recording.mp4"
    stored_bytes = storage.get_object_bytes(assembled_key)
    assert stored_bytes == expected_full_bytes

    # Cleanup live Garage S3 test objects if credentials are active
    if storage.access_key_id and storage.secret_access_key:
        s3 = storage._build_s3_client()
        for idx in range(8):
            s3.delete_object(
                Bucket=storage.bucket_name,
                Key=f"sessions/{session_id}/chunks/{idx}.mp4",
            )
        s3.delete_object(Bucket=storage.bucket_name, Key=assembled_key)
