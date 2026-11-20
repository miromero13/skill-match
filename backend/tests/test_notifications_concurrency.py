"""Independent connections in a disposable PostgreSQL schema, no public migration."""
import asyncio
from datetime import timedelta
from pathlib import Path
import re
from types import SimpleNamespace
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.security import create_access_token
from app.db.session import get_db
from app.main import create_application
from app.models.user import User
from test_notifications import DEFAULTS, LIST, PREFS, assert_error

pytestmark = pytest.mark.hu25


@pytest.fixture
async def concurrent_inbox():
    app = create_application()
    assert PREFS in app.openapi()["paths"], "HU-25 preferences route not implemented"
    assert settings.ENVIRONMENT == "development"
    admin_engine = create_async_engine(settings.async_database_url)
    assert admin_engine.url.host in {"localhost", "127.0.0.1", "::1"}
    schema = "hu25_test_" + uuid4().hex
    assert re.fullmatch(r"hu25_test_[0-9a-f]{32}", schema)
    isolated = create_async_engine(settings.async_database_url, connect_args={"server_settings": {"search_path": schema}})
    created = False
    try:
        async with admin_engine.begin() as connection:
            before = await connection.run_sync(lambda c: inspect(c).get_table_names(schema="public"))
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        created = True
        async with isolated.connect() as connection:
            assert await connection.scalar(text("SELECT current_schema()")) == schema
            await connection.commit()

            def migrate(sync_connection):
                config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
                config.attributes["connection"] = sync_connection
                command.upgrade(config, "head")

            await connection.run_sync(migrate)
        sessions = async_sessionmaker(isolated, expire_on_commit=False)
        async with sessions() as db:
            user = User(id=uuid4(), email=f"hu25-concurrent-{uuid4().hex}@example.invalid", full_name="HU25 concurrency", role="MEMBER", is_active=True, is_locked=False)
            db.add(user)
            await db.commit()

        async def request_db():
            async with sessions() as db:
                try:
                    yield db
                    await db.commit()
                except Exception:
                    await db.rollback()
                    raise

        app.dependency_overrides[get_db] = request_db
        token = create_access_token(str(user.id), "MEMBER", timedelta(minutes=5))
        async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://testserver") as client:
            yield SimpleNamespace(client=client, headers={"Authorization": "Bearer " + token}, user_id=user.id, sessions=sessions)
    finally:
        app.dependency_overrides.clear()
        await isolated.dispose()
        if created:
            async with admin_engine.begin() as connection:
                assert re.fullmatch(r"hu25_test_[0-9a-f]{32}", schema)
                await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
                assert await connection.run_sync(lambda c: inspect(c).get_table_names(schema="public")) == before
                assert await connection.scalar(text("SELECT count(*) FROM pg_namespace WHERE nspname = :schema"), {"schema": schema}) == 0
        await admin_engine.dispose()


async def test_two_initial_preference_updates_have_one_winner(concurrent_inbox):
    api = concurrent_inbox
    responses = await asyncio.gather(*[
        api.client.put(PREFS, headers=api.headers, json=DEFAULTS) for _ in range(2)
    ])
    assert sorted(r.status_code for r in responses) == [200, 409]
    assert_error(next(r for r in responses if r.status_code == 409), 409)
    response = await api.client.get(PREFS, headers=api.headers)
    assert response.json()["data"]["revision"] == 1


async def test_concurrent_duplicate_emission_persists_one_notice(concurrent_inbox):
    from app.services.notification_service import NotificationService
    api = concurrent_inbox
    event = uuid4()

    async def emit():
        async with api.sessions() as db:
            item = await NotificationService.emit_in_app(db, user_id=api.user_id, event_id=event,
                notification_type="MATCH_RECEIVED", title="Concurrent", message="Same event")
            await db.commit()
            return item.id

    outcomes = await asyncio.gather(emit(), emit())
    assert outcomes[0] == outcomes[1]
    response = await api.client.get(LIST, headers=api.headers)
    assert response.status_code == 200 and response.json()["count"] == 1
