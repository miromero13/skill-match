from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import WebSocketDisconnect
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.core.security import create_access_token
from app.db.session import get_db
from app.football.api.router import session_websocket_endpoint
from app.football.config import load_football_config
from app.football.pipeline.challenge_engine import generate_plan, verify_signed_plan
from app.football.services.storage import GarageS3StorageService
from app.football.tasks import celery_app, process_session
from app.main import create_application
from app.models.user import User, UserRole


class FakeWebSocket:
    """Lightweight in-process WebSocket harness for deterministic async testing."""

    def __init__(
        self,
        app: Any,
        inbound_messages: list[dict[str, Any]],
        headers: dict[str, str] | None = None,
    ) -> None:
        self.app = app
        self._inbound = list(inbound_messages)
        self.headers = headers or {}
        self.accepted = False
        self.closed_code: int | None = None
        self.sent_messages: list[dict[str, Any]] = []

    async def accept(self) -> None:
        self.accepted = True

    async def close(self, code: int = 1000) -> None:
        self.closed_code = code

    async def send_json(self, data: dict[str, Any]) -> None:
        self.sent_messages.append(data)

    async def receive_json(self) -> dict[str, Any]:
        if not self._inbound:
            raise WebSocketDisconnect(code=1000)
        return self._inbound.pop(0)


@pytest.fixture
async def football_api() -> AsyncGenerator[dict[str, Any], None]:
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
                        email=f"football-member-{suffix}@skillmatch.io",
                        full_name="Jugador Prueba Fase 0",
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


def test_config_and_challenge_plan_signature() -> None:
    cfg = load_football_config("development")
    assert len(cfg.config_hash) == 64
    assert cfg.session.max_attempts_per_window >= 1

    segments, signed_plan = generate_plan(seed=424242)
    assert cfg.challenges.min_segments <= len(segments) <= cfg.challenges.max_segments
    for idx in range(1, len(segments)):
        assert segments[idx]["tipo"] != segments[idx - 1]["tipo"]
    assert verify_signed_plan(signed_plan) is True
    assert verify_signed_plan(signed_plan.replace("LOW", "HIGH", 1)) is False


def test_garage_s3_storage_fallback_and_signed_url(tmp_path: Path) -> None:
    storage = GarageS3StorageService(
        endpoint_url="http://garage.coolify.internal:3900",
        bucket_name="skillmatch-football-test",
        local_fallback_dir=tmp_path,
    )
    payload = b"synthetic-video-chunk-phase0"
    uri, sha256_hex = storage.put_object_bytes(
        object_key="sessions/test-session/chunks/0.mp4",
        payload=payload,
        content_type="video/mp4",
        prefer_local=True,
    )
    assert uri == "s3://skillmatch-football-test/sessions/test-session/chunks/0.mp4"
    assert len(sha256_hex) == 64

    signed_url = storage.generate_signed_url(
        "sessions/test-session/chunks/0.mp4", expires_in_seconds=300
    )
    assert "http://garage.coolify.internal:3900/skillmatch-football-test/" in signed_url
    assert (
        "X-Amz-Signature=" in signed_url or "X-SkillMatch-Signature=" in signed_url
    )


def test_live_garage_s3_roundtrip_if_configured() -> None:
    storage = GarageS3StorageService()
    if not (storage.access_key_id and storage.secret_access_key):
        pytest.skip("Garage S3 credentials not configured")

    test_key = f"tests/phase0-roundtrip-{uuid.uuid4().hex[:8]}.bin"
    payload = b"skillmatch-phase0-live-garage-s3-check"
    uri, sha256_hex = storage.put_object_bytes(
        object_key=test_key,
        payload=payload,
        content_type="application/octet-stream",
    )
    assert uri == f"s3://{storage.bucket_name}/{test_key}"
    assert len(sha256_hex) == 64

    s3 = storage._build_s3_client()
    try:
        fetched = s3.get_object(Bucket=storage.bucket_name, Key=test_key)
        assert fetched["Body"].read() == payload
        assert fetched["Metadata"].get("sha256") == sha256_hex
    finally:
        s3.delete_object(Bucket=storage.bucket_name, Key=test_key)


def test_celery_test_task_runs_eagerly() -> None:
    celery_app.conf.task_always_eager = True
    fake_session_id = str(uuid.uuid4())
    async_result = process_session.delay(fake_session_id)
    result_payload = async_result.get(timeout=5)
    assert result_payload["session_id"] == fake_session_id
    assert result_payload["status"] == "processed_phase0_stub"
    assert len(result_payload["config_hash"]) == 64


@pytest.mark.asyncio
async def test_post_sessions_get_status_and_websocket(
    football_api: dict[str, Any],
) -> None:
    client: AsyncClient = football_api["client"]
    token: str = football_api["member_token"]
    app_instance = football_api["app"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create session via /api/v1/football/sessions
    resp = await client.post("/api/v1/football/sessions", headers=headers, json={})
    assert resp.status_code == 201
    body = resp.json()
    assert body["statuscode"] == 201
    session_data = body["data"]
    session_id = session_data["session_id"]
    assert session_data["estado"] == "created"
    assert session_data["semilla"] > 0
    assert session_data["ws_url"].endswith(f"/sessions/{session_id}/ws")

    # 2. Fetch status via /api/football/sessions/{id}
    status_resp = await client.get(
        f"/api/football/sessions/{session_id}",
        headers=headers,
    )
    assert status_resp.status_code == 200
    status_body = status_resp.json()
    assert status_body["data"]["id"] == session_id
    assert len(status_body["data"]["segments"]) >= 4

    # 3. Connect to WebSocket, receive status & command, send ping & client_event
    fake_ws = FakeWebSocket(
        app=app_instance,
        inbound_messages=[
            {"type": "ping", "timestamp_ms": 1234},
            {
                "type": "client_event",
                "event": "tab_hidden",
                "timestamp_ms": 4500,
            },
        ],
    )
    mock_ws: Any = MagicMock(wraps=fake_ws)
    mock_ws.app = app_instance
    mock_ws.headers = fake_ws.headers
    mock_ws.accept = fake_ws.accept
    mock_ws.close = fake_ws.close
    mock_ws.send_json = fake_ws.send_json
    mock_ws.receive_json = fake_ws.receive_json

    await session_websocket_endpoint(
        websocket=mock_ws,
        session_id=uuid.UUID(session_id),
        token=token,
    )

    assert fake_ws.accepted is True
    assert len(fake_ws.sent_messages) == 4
    assert fake_ws.sent_messages[0]["type"] == "status"
    assert fake_ws.sent_messages[0]["data"]["estado"] == "created"
    assert fake_ws.sent_messages[1]["type"] == "command"
    assert fake_ws.sent_messages[1]["data"]["indice"] == 0
    assert fake_ws.sent_messages[2]["type"] == "pong"
    assert fake_ws.sent_messages[2]["data"]["timestamp_ms"] == 1234
    assert fake_ws.sent_messages[3]["type"] == "status"
    assert fake_ws.sent_messages[3]["data"]["recorded_event"] == "tab_hidden"
    assert fake_ws.sent_messages[3]["data"]["t_ms"] == 4500
