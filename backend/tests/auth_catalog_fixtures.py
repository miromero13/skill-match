"""Isolate acceptance probes inside an uncommitted PostgreSQL schema."""
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app import models as registered_models  # Register tables without shadowing the ASGI app.


@pytest.fixture
async def isolated_db():
    engine = create_async_engine(settings.async_database_url)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        schema = f"test_auth_catalog_{uuid.uuid4().hex}"
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        await connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
        await connection.run_sync(Base.metadata.create_all)
        session = AsyncSession(bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
        async def dependency():
            yield session
        app.dependency_overrides[get_db] = dependency
        try:
            yield session
        finally:
            app.dependency_overrides.pop(get_db, None)
            await session.close()
            await transaction.rollback()
    await engine.dispose()
