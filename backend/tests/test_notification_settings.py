"""S7 regression: notification Settings (SMTP + Web Push/VAPID) restored from f19619d."""

from contextlib import asynccontextmanager
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr, ValidationError
from sqlalchemy import delete

from app.api.notifications import web_push as web_push_api
from app.core.config import Settings
from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.main import create_application
from app.models.user import User, UserRole

NOTIFICATION_ENV_VARS = (
    "EMAIL_ENABLED",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
    "SMTP_STARTTLS",
    "SMTP_TIMEOUT_SECONDS",
    "EMAIL_FROM_ADDRESS",
    "EMAIL_FROM_NAME",
    "EMAIL_REPLY_TO",
    "FRONTEND_BASE_URL",
    "WEB_PUSH_ENABLED",
    "VAPID_PUBLIC_KEY",
    "VAPID_PRIVATE_KEY",
    "VAPID_SUBJECT",
)

REQUIRED = {
    "PROJECT_NAME": "SkillMatch Test",
    "VERSION": "0.0.0",
    "ENVIRONMENT": "test",
    "DEBUG": False,
    "ALLOWED_ORIGINS": "http://localhost:5173",
    "POSTGRES_HOST": "localhost",
    "POSTGRES_PORT": 5432,
    "POSTGRES_USER": "test",
    "POSTGRES_PASSWORD": "test",
    "POSTGRES_DB": "test",
    "SECRET_KEY": "test-secret",
    "ADMIN_EMAIL": "admin@example.com",
    "ADMIN_PASSWORD": "test-password",
}

VALID_PUSH = {
    "WEB_PUSH_ENABLED": True,
    "VAPID_PUBLIC_KEY": "BPublicKeyUrlSafeBase64",
    "VAPID_PRIVATE_KEY": "private-key-url-safe-base64",
    "VAPID_SUBJECT": "mailto:soporte@skillmatch.io",
}


@pytest.fixture
def isolated_env(monkeypatch):
    """Keep OS env vars from leaking into the defaults under test."""
    for name in NOTIFICATION_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def build_settings(**overrides) -> Settings:
    return Settings(_env_file=None, **{**REQUIRED, **overrides})


def test_notification_settings_expose_restored_defaults(isolated_env):
    loaded = build_settings()

    assert loaded.EMAIL_ENABLED is False
    assert loaded.SMTP_HOST == "smtp.gmail.com"
    assert loaded.SMTP_PORT == 587
    assert loaded.SMTP_USERNAME is None
    assert loaded.SMTP_PASSWORD is None
    assert loaded.SMTP_STARTTLS is True
    assert loaded.SMTP_TIMEOUT_SECONDS == 15
    assert loaded.EMAIL_FROM_ADDRESS is None
    assert loaded.EMAIL_FROM_NAME == "SkillMatch"
    assert loaded.EMAIL_REPLY_TO is None
    assert loaded.FRONTEND_BASE_URL == "http://localhost:5173"
    assert loaded.WEB_PUSH_ENABLED is False
    assert loaded.VAPID_PUBLIC_KEY is None
    assert loaded.VAPID_PRIVATE_KEY is None
    assert loaded.VAPID_SUBJECT is None


def test_smtp_secrets_are_secret_strings(isolated_env):
    loaded = build_settings(SMTP_USERNAME="mailer", SMTP_PASSWORD="app-password")

    assert isinstance(loaded.SMTP_USERNAME, SecretStr)
    assert isinstance(loaded.SMTP_PASSWORD, SecretStr)
    assert loaded.SMTP_PASSWORD.get_secret_value() == "app-password"
    assert "app-password" not in repr(loaded)


@pytest.mark.parametrize(
    ("field", "value"),
    [("SMTP_PORT", 0), ("SMTP_PORT", 65536), ("SMTP_TIMEOUT_SECONDS", 0), ("SMTP_TIMEOUT_SECONDS", 121)],
)
def test_smtp_numeric_bounds_are_enforced(isolated_env, field, value):
    with pytest.raises(ValidationError) as error:
        build_settings(**{field: value})
    assert field in str(error.value)


@pytest.mark.parametrize("missing", ["VAPID_PUBLIC_KEY", "VAPID_PRIVATE_KEY", "VAPID_SUBJECT"])
def test_web_push_enabled_requires_every_vapid_value(isolated_env, missing):
    config = {**VALID_PUSH}
    config.pop(missing)

    with pytest.raises(ValidationError) as error:
        build_settings(**config)

    assert (
        "WEB_PUSH_ENABLED requiere VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY y VAPID_SUBJECT"
        in str(error.value)
    )


@pytest.mark.parametrize("subject", ["soporte@skillmatch.io", "http://skillmatch.io"])
def test_web_push_subject_must_be_mailto_or_https(isolated_env, subject):
    with pytest.raises(ValidationError) as error:
        build_settings(**{**VALID_PUSH, "VAPID_SUBJECT": subject})

    assert "VAPID_SUBJECT debe usar mailto: o https://" in str(error.value)


@pytest.mark.parametrize("subject", ["mailto:soporte@skillmatch.io", "https://skillmatch.io/contact"])
def test_complete_web_push_configuration_loads(isolated_env, subject):
    loaded = build_settings(**{**VALID_PUSH, "VAPID_SUBJECT": subject})

    assert loaded.WEB_PUSH_ENABLED is True
    assert loaded.VAPID_PUBLIC_KEY == VALID_PUSH["VAPID_PUBLIC_KEY"]
    assert isinstance(loaded.VAPID_PRIVATE_KEY, SecretStr)
    assert loaded.VAPID_PRIVATE_KEY.get_secret_value() == VALID_PUSH["VAPID_PRIVATE_KEY"]
    assert loaded.VAPID_SUBJECT == subject


def test_disabled_web_push_ignores_incomplete_vapid_values(isolated_env):
    loaded = build_settings(WEB_PUSH_ENABLED=False, VAPID_SUBJECT="not-a-contact")

    assert loaded.WEB_PUSH_ENABLED is False


@asynccontextmanager
async def _member():
    async with AsyncSessionLocal() as db:
        member = User(
            email=f"push-settings-{uuid4().hex}@example.invalid",
            full_name="Push Settings Member",
            role=UserRole.MEMBER,
        )
        db.add(member)
        await db.commit()
        await db.refresh(member)
    try:
        yield member
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(User).where(User.id == member.id))
            await db.commit()


@pytest.mark.asyncio(loop_scope="session")
async def test_public_key_endpoint_returns_503_envelope_when_web_push_disabled(isolated_env, monkeypatch):
    monkeypatch.setattr(web_push_api, "settings", build_settings(WEB_PUSH_ENABLED=False))

    async with _member() as member:
        token = create_access_token(str(member.id), UserRole.MEMBER.value)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_application()),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/notifications/push/public-key",
                headers={"Authorization": f"Bearer {token}"},
            )

    assert response.status_code == 503
    assert response.json() == {
        "statuscode": 503,
        "message": "Web Push no está configurado.",
        "data": None,
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_public_key_endpoint_returns_key_when_web_push_configured(isolated_env, monkeypatch):
    monkeypatch.setattr(web_push_api, "settings", build_settings(**VALID_PUSH))

    async with _member() as member:
        token = create_access_token(str(member.id), UserRole.MEMBER.value)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_application()),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/notifications/push/public-key",
                headers={"Authorization": f"Bearer {token}"},
            )

    assert response.status_code == 200
    payload = response.json()
    assert payload["statuscode"] == 200
    assert payload["data"] == {"public_key": VALID_PUSH["VAPID_PUBLIC_KEY"]}
