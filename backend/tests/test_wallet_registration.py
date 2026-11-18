import uuid

import pytest
from sqlalchemy import text

from auth_catalog_fixtures import isolated_db
from test_google_security import google_client


@pytest.mark.asyncio
async def test_registered_wallet_survives_identity_reload_and_has_no_bonus(google_client, isolated_db):
    client, _, _, _ = google_client
    registered = await client.post("/api/auth/oauth/google", json={"id_token": "verified-upstream"})
    assert registered.status_code == 200
    data = registered.json()["data"]
    user_id = uuid.UUID(data["user"]["id"])
    headers = {"Authorization": f'Bearer {data["access_token"]}'}
    isolated_db.expunge_all()
    identity = await client.get("/api/auth/me", headers=headers)
    assert identity.status_code == 200
    assert identity.json()["data"]["skill_points_balance"] == 0

    # Arrange a stored balance to prove /me reads persistence rather than a UI constant.
    await isolated_db.execute(text("UPDATE wallets SET balance=42 WHERE user_id=:id"), {"id": user_id})
    await isolated_db.commit()
    isolated_db.expunge_all()
    identity = await client.get("/api/auth/me", headers=headers)
    assert identity.status_code == 200
    assert identity.json()["data"]["skill_points_balance"] == 42
    again = await client.post("/api/auth/oauth/google", json={"id_token": "verified-upstream"})
    assert again.status_code == 200
    assert again.json()["data"]["user"]["id"] == str(user_id)
    assert again.json()["data"]["user"]["skill_points_balance"] == 42
