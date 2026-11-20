"""PostgreSQL/API contracts for private Web Push device subscriptions."""

from contextlib import asynccontextmanager
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import delete

from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.main import create_application
from app.models.user import User, UserRole


def _headers(user: User) -> dict[str, str]:
    token = create_access_token(str(user.id), UserRole.MEMBER.value)
    return {"Authorization": f"Bearer {token}"}


def _subscription(suffix: str) -> dict:
    return {
        "endpoint": f"https://push.example.test/send/{suffix}",
        "keys": {"p256dh": f"public-{suffix}", "auth": f"auth-{suffix}"},
        "device_label": f"Device {suffix}",
    }


def _envelope(response: httpx.Response, statuscode: int) -> dict:
    assert response.status_code == statuscode
    payload = response.json()
    assert payload["statuscode"] == statuscode
    assert isinstance(payload["message"], str) and payload["message"].strip()
    assert "data" in payload
    assert "error" not in payload
    return payload


@asynccontextmanager
async def _users():
    suffix = uuid4().hex
    async with AsyncSessionLocal() as db:
        owner = User(
            email=f"push-owner-{suffix}@example.invalid",
            full_name="Push Owner",
            role=UserRole.MEMBER,
        )
        outsider = User(
            email=f"push-outsider-{suffix}@example.invalid",
            full_name="Push Outsider",
            role=UserRole.MEMBER,
        )
        db.add_all([owner, outsider])
        await db.commit()
        await db.refresh(owner)
        await db.refresh(outsider)
    try:
        yield owner, outsider
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(User).where(User.id.in_([owner.id, outsider.id])))
            await db.commit()


@pytest.mark.asyncio(loop_scope="session")
async def test_member_registers_multiple_devices_and_retry_is_idempotent():
    async with _users() as (owner, outsider):
        app = create_application()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            url = "/api/notifications/push/subscriptions"
            _envelope(await client.post(url, json=_subscription("one")), 401)
            first = _envelope(
                await client.post(url, headers=_headers(owner), json=_subscription("one")),
                201,
            )["data"]
            replay = _envelope(
                await client.post(url, headers=_headers(owner), json=_subscription("one")),
                200,
            )["data"]
            second = _envelope(
                await client.post(url, headers=_headers(owner), json=_subscription("two")),
                201,
            )["data"]

            assert replay["id"] == first["id"]
            assert second["id"] != first["id"]
            assert first["endpoint"] != _subscription("one")["endpoint"]
            assert "p256dh" not in first
            assert "auth" not in first

            conflict = await client.post(
                url,
                headers=_headers(outsider),
                json=_subscription("one"),
            )
            _envelope(conflict, 409)


@pytest.mark.asyncio(loop_scope="session")
async def test_member_revokes_only_an_owned_subscription_with_404_obfuscation():
    async with _users() as (owner, outsider):
        app = create_application()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            created = _envelope(
                await client.post(
                    "/api/notifications/push/subscriptions",
                    headers=_headers(owner),
                    json=_subscription("owned"),
                ),
                201,
            )["data"]
            url = f"/api/notifications/push/subscriptions/{created['id']}"
            _envelope(await client.delete(url, headers=_headers(outsider)), 404)
            _envelope(await client.delete(url, headers=_headers(owner)), 200)
            _envelope(await client.delete(url, headers=_headers(owner)), 404)
