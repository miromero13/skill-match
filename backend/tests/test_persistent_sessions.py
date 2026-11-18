"""Session security through HTTP, with real string roles and isolated PostgreSQL."""
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, clear_revoked_tokens
from app.main import app
from app.models.user import User
from auth_catalog_fixtures import isolated_db


async def member(db, role="MEMBER"):
    user = User(id=uuid.uuid4(), email=f"{uuid.uuid4().hex}@example.com", full_name="Session User",
                role=role, is_active=True, is_locked=False)
    db.add(user)
    await db.commit()
    db.expunge_all()
    return user


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["MEMBER", "ADMIN"])
async def test_refresh_preserves_persisted_string_role_and_cannot_replay_after_cache_reset(isolated_db, role):
    user = await member(isolated_db, role)
    refresh = create_refresh_token(str(user.id), role)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post("/api/auth/refresh", json={"refresh_token": refresh})
        assert response.status_code == 200
        data = response.json()["data"]
        for kind in ("access", "refresh"):
            claims = jwt.decode(data[f"{kind}_token"], settings.SECRET_KEY.get_secret_value(), algorithms=[settings.ALGORITHM])
            assert claims["role"] == role
            assert claims["type"] == kind
            assert claims["sub"] == str(user.id)
        clear_revoked_tokens()
        isolated_db.expunge_all()
        replay = await client.post("/api/auth/refresh", json={"refresh_token": refresh})
        assert replay.status_code == 401
        assert replay.json()["data"] is None
        assert (await client.get("/api/auth/me", headers={"Authorization": f'Bearer {data["access_token"]}'})).status_code == 200


@pytest.mark.asyncio
async def test_failed_issuance_does_not_consume_refresh(isolated_db, monkeypatch):
    user = await member(isolated_db, "ADMIN")
    refresh = create_refresh_token(str(user.id), "ADMIN")
    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://testserver") as client:
        with monkeypatch.context() as patch:
            def fail(**kwargs):
                raise RuntimeError("simulated signing failure")
            patch.setattr("app.services.auth_service.create_refresh_token", fail)
            failed = await client.post("/api/auth/refresh", json={"refresh_token": refresh})
            assert failed.status_code == 500
        retry = await client.post("/api/auth/refresh", json={"refresh_token": refresh})
        assert retry.status_code == 200


@pytest.mark.asyncio
async def test_logout_survives_process_local_cache_reset(isolated_db):
    user = await member(isolated_db)
    access = create_access_token(str(user.id), "MEMBER")
    refresh = create_refresh_token(str(user.id), "MEMBER")
    headers = {"Authorization": f"Bearer {access}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post("/api/auth/logout", headers=headers, json={"refresh_token": refresh})
        assert response.status_code == 200
        clear_revoked_tokens()
        isolated_db.expunge_all()
        assert (await client.get("/api/auth/me", headers=headers)).status_code == 401
        assert (await client.post("/api/auth/refresh", json={"refresh_token": refresh})).status_code == 401


@pytest.mark.asyncio
async def test_logout_rejects_someone_elses_refresh_without_revoking_either_user(isolated_db):
    owner = await member(isolated_db)
    other = await member(isolated_db)
    access = create_access_token(str(owner.id), "MEMBER")
    refresh = create_refresh_token(str(other.id), "MEMBER")
    headers = {"Authorization": f"Bearer {access}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post("/api/auth/logout", headers=headers, json={"refresh_token": refresh})
        assert response.status_code == 401
        assert response.json()["message"] == "El token de renovación no pertenece a esta sesión."
        assert response.json()["data"] is None
        assert (await client.get("/api/auth/me", headers=headers)).status_code == 200
        assert (await client.post("/api/auth/refresh", json={"refresh_token": refresh})).status_code == 200
