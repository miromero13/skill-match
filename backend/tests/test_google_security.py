"""Public Google login contract: no unsigned fallback or administrator promotion."""
import time
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from jose import jwt

from app.core.config import settings
from app.db.session import get_db
from app.main import app
from app.models.user import User
from test_member_auth import MockDbSession, create_mock_google_token


class RecordingSession(MockDbSession):
    def __init__(self, user=None):
        super().__init__(user)
        self.added = []

    def add(self, entity):
        self.added.append(entity)
        super().add(entity)

    async def flush(self):
        pass


@pytest.fixture
async def google_client(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "skillmatch-test.apps.googleusercontent.com")
    verified = {
        "iss": "https://accounts.google.com", "aud": settings.GOOGLE_CLIENT_ID,
        "sub": "google-sub-123", "email": "member@example.com", "email_verified": "true",
        "name": "Member", "exp": str(int(time.time()) + 3600),
    }
    upstream = SimpleNamespace(status_code=200, json=lambda: verified, text="rejected")
    verifier = AsyncMock()
    verifier.get.return_value = upstream
    context = AsyncMock()
    context.__aenter__.return_value = verifier
    monkeypatch.setattr("app.services.auth_service.httpx.AsyncClient", lambda **_: context)
    async with httpx_client(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        yield client, verified, upstream, verifier
    app.dependency_overrides.pop(get_db, None)


httpx_client = httpx.AsyncClient


def use_session(session):
    async def dependency():
        yield session
    app.dependency_overrides[get_db] = dependency


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["google_rejected", "audience", "issuer", "unverified", "expired", "missing_subject"])
async def test_google_rejects_unverified_identity_without_writes(google_client, failure):
    client, claims, upstream, _ = google_client
    session = RecordingSession()
    use_session(session)
    if failure == "google_rejected":
        upstream.status_code = 400
    elif failure == "audience":
        claims["aud"] = "other-client"
    elif failure == "issuer":
        claims["iss"] = "https://attacker.example"
    elif failure == "unverified":
        claims["email_verified"] = "false"
    elif failure == "expired":
        claims["exp"] = "1"
    else:
        claims.pop("sub")
    response = await client.post("/api/auth/oauth/google", json={"id_token": create_mock_google_token("member@example.com", "Member")})
    assert response.status_code == 401
    assert response.json()["statuscode"] == 401
    assert response.json()["data"] is None
    assert session.added == []


@pytest.mark.asyncio
@pytest.mark.parametrize("role,subject", [("ADMIN", None), ("MEMBER", "another-google-subject")])
async def test_google_cannot_claim_admin_or_another_google_identity(google_client, role, subject):
    client, _, _, _ = google_client
    user = User(id=uuid.uuid4(), email="member@example.com", full_name="Original", role=role,
                is_active=True, is_locked=False, provider="google" if subject else None,
                provider_user_id=subject, hashed_password="existing-password" if role == "ADMIN" else None)
    session = RecordingSession(user)
    use_session(session)
    response = await client.post("/api/auth/oauth/google", json={"id_token": "verified-upstream"})
    assert response.status_code == 401
    assert response.json()["data"] is None
    assert user.full_name == "Original"
    assert user.provider_user_id == subject
    assert user.role == role
    assert session.added == []


@pytest.mark.asyncio
async def test_google_registration_creates_member_and_zero_wallet(google_client):
    client, _, _, _ = google_client
    session = RecordingSession()
    use_session(session)
    response = await client.post("/api/auth/oauth/google", json={"id_token": "verified-upstream"})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["user"]["role"] == "MEMBER"
    assert data["user"]["skill_points_balance"] == 0
    wallet = next(entity for entity in session.added if entity.__class__.__name__ == "Wallet")
    assert str(wallet.user_id) == data["user"]["id"]
    assert wallet.balance == 0
    member = session.added_users[0]
    assert member.hashed_password is None
    for kind in ("access", "refresh"):
        claims = jwt.decode(data[f"{kind}_token"], settings.SECRET_KEY.get_secret_value(), algorithms=[settings.ALGORITHM])
        assert claims["role"] == "MEMBER"
        assert claims["type"] == kind


@pytest.mark.asyncio
async def test_google_credential_is_not_written_to_http_client_logs(google_client, monkeypatch, caplog):
    client, claims, _, _ = google_client
    use_session(RecordingSession())
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=claims))
    monkeypatch.setattr("app.services.auth_service.httpx.AsyncClient", lambda **kwargs: httpx_client(transport=transport, **kwargs))
    credential = "sensitive-google-credential-not-for-logs"
    response = await client.post("/api/auth/oauth/google", json={"id_token": credential})
    assert response.status_code == 200
    assert credential not in caplog.text
