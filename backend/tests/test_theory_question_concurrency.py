"""Optimistic question revisions are serialized over independent HTTP sessions."""
import asyncio
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.core.security import create_access_token
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import Category, Skill, SkillLevel, User, UserRole
from test_theory_question_publication import complete


@pytest.mark.asyncio
async def test_concurrent_edit_creates_exactly_one_new_version():
    if not settings.POSTGRES_DB.startswith("suite_hardening_"):
        pytest.skip("Requires disposable runner; never commits schema/data to application database")
    schema = "theory_race_" + uuid.uuid4().hex
    engine = create_async_engine(settings.async_database_url,
                                 connect_args={"server_settings": {"search_path": schema}})
    try:
        async with engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            await connection.run_sync(Base.metadata.create_all)
        async with AsyncSession(engine, expire_on_commit=False) as db:
            admin = User(email=f"{uuid.uuid4()}@example.test", full_name="Admin", role=UserRole.ADMIN)
            category = Category(name="Theory", slug=str(uuid.uuid4()))
            db.add_all([admin, category])
            await db.flush()
            skill = Skill(name="Python", slug=str(uuid.uuid4()), category_id=category.id)
            db.add(skill)
            await db.flush()
            db.add(SkillLevel(skill_id=skill.id, level_number=1, name="Principiante"))
            await db.commit()
            token = create_access_token(subject=str(admin.id), role="ADMIN")
            skill_id = str(skill.id)

        async def dependency():
            async with AsyncSession(engine, expire_on_commit=False) as db:
                yield db

        app.dependency_overrides[get_db] = dependency
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test",
                               headers={"Authorization": f"Bearer {token}"}) as client:
            root = "/api/admin/theory/questions"
            created = await client.post(root, json={"skill_id": skill_id, "level_number": 1, **complete()})
            assert created.status_code == 201
            original = created.json()["data"]
            path = f"{root}/{original['id']}"
            payloads = [{"expected_version": 1, "content": {**complete(), "prompt": prompt}}
                        for prompt in ["First editor", "Second editor"]]
            responses = await asyncio.gather(*(client.patch(path, json=payload) for payload in payloads))
            assert sorted(r.status_code for r in responses) == [200, 409]
            winner = next(i for i, response in enumerate(responses) if response.status_code == 200)
            conflict = responses[1 - winner]
            assert conflict.json() == {"statuscode": 409, "message": "La pregunta cambió. Recargá la última versión antes de guardar.", "data": None}
            expected = {**original, "version": 2, "content": payloads[winner]["content"]}
            assert responses[winner].json() == {"statuscode": 200, "message": "Nueva versión de pregunta creada.", "data": expected}
            history = await client.get(path + "/versions")
            assert history.status_code == 200
            assert history.json() == {"statuscode": 200, "message": "Versiones de pregunta recuperadas exitosamente.",
                                      "data": [original, expected], "count": 2}
            latest = await client.get(path)
            assert latest.status_code == 200 and latest.json()["data"] == expected
            listing = await client.get(root)
            assert listing.status_code == 200 and listing.json()["count"] == 1
            assert listing.json()["data"] == [expected]
    finally:
        app.dependency_overrides.pop(get_db, None)
        async with engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await engine.dispose()
