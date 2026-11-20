"""Tests for mobile device push tokens (FCM) and FCM notification service."""

from contextlib import asynccontextmanager
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import delete

from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.main import create_application
from app.models.device_push_token import DevicePushToken
from app.models.user import User, UserRole


def _headers(user: User) -> dict[str, str]:
    token = create_access_token(str(user.id), UserRole.MEMBER.value)
    return {"Authorization": f"Bearer {token}"}


@asynccontextmanager
async def _user():
    suffix = uuid4().hex
    async with AsyncSessionLocal() as db:
        user = User(
            email=f"fcm-user-{suffix}@example.invalid",
            full_name="FCM Test User",
            role=UserRole.MEMBER,
        )
        admin = User(
            email=f"fcm-admin-{suffix}@example.invalid",
            full_name="FCM Admin User",
            role=UserRole.ADMIN,
        )
        db.add_all([user, admin])
        await db.commit()
        await db.refresh(user)
        await db.refresh(admin)

    try:
        yield user, admin
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(DevicePushToken).where(DevicePushToken.user_id.in_([user.id, admin.id])))
            await db.execute(delete(User).where(User.id.in_([user.id, admin.id])))
            await db.commit()


@pytest.mark.asyncio
async def test_register_and_deactivate_device_push_token():
    app = create_application()
    transport = httpx.ASGITransport(app=app)
    async with (
        httpx.AsyncClient(transport=transport, base_url="http://test") as client,
        _user() as (member, admin),
    ):
        token_val = f"test-fcm-token-{uuid4().hex}"

        # 1. Anonymous user is denied (401)
        res = await client.post("/api/notifications/devices", json={"fcm_token": token_val, "platform": "android"})
        assert res.status_code == 401

        # 2. Admin is obfuscated (404)
        admin_token = create_access_token(str(admin.id), UserRole.ADMIN.value)
        res = await client.post(
            "/api/notifications/devices",
            json={"fcm_token": token_val, "platform": "android"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res.status_code == 404

        # 3. Member successfully registers FCM token (201)
        res = await client.post(
            "/api/notifications/devices",
            json={"fcm_token": token_val, "platform": "android", "device_label": "Infinix Test"},
            headers=_headers(member),
        )
        assert res.status_code == 201
        body = res.json()
        assert body["statuscode"] == 201
        assert body["data"]["platform"] == "android"
        assert body["data"]["device_label"] == "Infinix Test"
        assert body["data"]["is_active"] is True

        # 4. Member deactivates token (200)
        res = await client.delete(
            f"/api/notifications/devices/{token_val}",
            headers=_headers(member),
        )
        assert res.status_code == 200
        assert res.json()["statuscode"] == 200
