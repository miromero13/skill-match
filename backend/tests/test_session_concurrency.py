"""Competing requests use independent database sessions, as separate workers do."""
import asyncio
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.security import create_refresh_token
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.user import User


@pytest.mark.asyncio
async def test_exactly_one_concurrent_refresh_wins():
    schema = f"test_refresh_race_{uuid.uuid4().hex}"
    engine = create_async_engine(settings.async_database_url, connect_args={"server_settings": {"search_path": schema}})
    try:
        async with engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            await connection.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        user_id = uuid.uuid4()
        async with sessions() as session:
            session.add(User(id=user_id, email="race@example.com", full_name="Race Member", role="MEMBER", is_active=True, is_locked=False))
            await session.commit()
        async def dependency():
            async with sessions() as session:
                yield session
        app.dependency_overrides[get_db] = dependency
        credential = create_refresh_token(str(user_id), "MEMBER")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            responses = await asyncio.gather(*[
                client.post("/api/auth/refresh", json={"refresh_token": credential}) for _ in range(2)
            ])
            assert sorted(response.status_code for response in responses) == [200, 401]
            winner = next(response.json()["data"] for response in responses if response.status_code == 200)
            assert (await client.get("/api/auth/me", headers={"Authorization": f'Bearer {winner["access_token"]}'})).status_code == 200
            assert (await client.post("/api/auth/refresh", json={"refresh_token": credential})).status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)
        async with engine.begin() as connection:
            # The UUID schema is created by this test alone, never the application's schema.
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await engine.dispose()
