"""Actual concurrent public HTTP checks, only in the disposable suite database."""
import asyncio
import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.core.security import create_access_token
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import User, UserRole


@pytest.mark.asyncio
async def test_concurrent_claim_and_duplicate_ingestion():
    if not settings.POSTGRES_DB.startswith("suite_hardening_"):
        pytest.skip("Requires the disposable DB runner; never creates committed schemas in application DB")
    schema = "browser_race_" + uuid.uuid4().hex
    engine = create_async_engine(settings.async_database_url, connect_args={"server_settings": {"search_path": schema}})
    try:
        async with engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            await connection.run_sync(Base.metadata.create_all)
        async with AsyncSession(engine, expire_on_commit=False) as db:
            user = User(email=f"{uuid.uuid4()}@example.test", full_name="Concurrent member", role=UserRole.MEMBER)
            db.add(user)
            await db.commit()
            token = create_access_token(subject=str(user.id), role="MEMBER")

        async def dependency():
            async with AsyncSession(engine, expire_on_commit=False) as db:
                yield db

        app.dependency_overrides[get_db] = dependency
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test",
                               headers={"Authorization": f"Bearer {token}"}) as client:
            root = "/api/browser-supervision/trials"
            tabs = [str(uuid.uuid4()), str(uuid.uuid4())]
            claims = await asyncio.gather(*(client.post(root, json={"tab_id": tab, "accepted": True}) for tab in tabs))
            assert sorted(response.status_code for response in claims) == [200, 409]
            winner = next(i for i, response in enumerate(claims) if response.status_code == 200)
            trial = claims[winner].json()["data"]
            payload = {"tab_id": tabs[winner], "events": [{"event_id": str(uuid.uuid4()), "kind": "PASTE",
                                                          "observed_at": datetime.now(timezone.utc).isoformat()}]}
            responses = await asyncio.gather(*(client.post(f"{root}/{trial['id']}/events", json=payload) for _ in range(2)))
            assert all(response.status_code == 200 for response in responses)
            assert responses[0].json() == responses[1].json()
            log = (await client.get(f"{root}/{trial['id']}/events")).json()
            assert log["count"] == len(log["data"]) == 1
            assert log["data"][0]["sequence"] == 1
    finally:
        app.dependency_overrides.pop(get_db, None)
        async with engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await engine.dispose()
