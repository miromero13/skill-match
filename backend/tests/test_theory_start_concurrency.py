"""Real independent-connection HTTP requests race the same exam start."""
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
from app.models import Category, Evaluation, Skill, TeachingSkill, User, UserRole
from test_evaluation_preflight import CONSENT
from test_theory_exam_start import prepare, ready_runtime


@pytest.mark.asyncio
@pytest.mark.parametrize("race", ["same", "quota"])
async def test_concurrent_starts_replay_one_fixed_exam(race):
    if not settings.POSTGRES_DB.startswith("suite_hardening_"):
        pytest.skip("Requires disposable database runner")
    schema = "theory_start_" + uuid.uuid4().hex
    engine = create_async_engine(settings.async_database_url,
                                 connect_args={"server_settings": {"search_path": schema}})
    try:
        async with engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            await connection.run_sync(Base.metadata.create_all)
        async with AsyncSession(engine, expire_on_commit=False) as db:
            user = User(email=f"{uuid.uuid4()}@example.test", full_name="Member", role=UserRole.MEMBER,
                        biometric_embedding="[0.1]", biometric_face_hash="reference")
            category = Category(name="Theory", slug=str(uuid.uuid4()), is_active=True)
            db.add_all([user, category])
            await db.flush()
            skill = Skill(name="Python", slug=str(uuid.uuid4()), category_id=category.id, is_active=True)
            db.add(skill)
            await db.flush()
            offer = TeachingSkill(user_id=user.id, skill_id=skill.id, declared_level="BEGINNER",
                                  years_of_experience=1, accepts_points=False)
            db.add(offer)
            await db.commit()
            token = create_access_token(subject=str(user.id), role="MEMBER")
            offer_id = str(offer.id)

        async def dependency():
            async with AsyncSession(engine, expire_on_commit=False) as session:
                yield session

        app.dependency_overrides[get_db] = dependency
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test",
                               headers={"Authorization": f"Bearer {token}"}) as client:
            root = f"/api/evaluations/skills/{offer_id}"
            consent = await client.post(root + "/consent", json=CONSENT)
            assert consent.status_code == 200
            key = consent.json()["data"]["id"]
            async with AsyncSession(engine, expire_on_commit=False) as db:
                await prepare(db, user, offer, key)
            keys = [key, key]
            if race == "quota":
                async with AsyncSession(engine, expire_on_commit=False) as db:
                    other_skill = Skill(name="Other", slug=str(uuid.uuid4()), category_id=category.id, is_active=True)
                    db.add(other_skill)
                    await db.flush()
                    other_offer = TeachingSkill(user_id=user.id, skill_id=other_skill.id, declared_level="BEGINNER",
                                                years_of_experience=1, accepts_points=False)
                    db.add(other_offer)
                    await db.commit()
                other_consent = await client.post(f"/api/evaluations/skills/{other_offer.id}/consent", json=CONSENT)
                assert other_consent.status_code == 200
                keys[1] = other_consent.json()["data"]["id"]
                async with AsyncSession(engine, expire_on_commit=False) as db:
                    await prepare(db, user, other_offer, keys[1])
                    for index in range(2):
                        used_skill = Skill(name=f"Spent {index}", slug=str(uuid.uuid4()), category_id=category.id)
                        db.add(used_skill)
                        await db.flush()
                        db.add(Evaluation(user_id=user.id, skill_id=used_skill.id, status="COMPLETED",
                                          biometric_consent_at=datetime.now(timezone.utc), policy_version="v1.0",
                                          ip_address="test", user_agent="test", started_at=datetime.now(timezone.utc)))
                    await db.commit()
            responses = await asyncio.gather(*(client.post("/api/evaluations/start",
                json={"evaluation_id": exam_key, "level_number": 1}) for exam_key in keys))
            if race == "same":
                assert [r.status_code for r in responses] == [200, 200]
                assert responses[0].json() == responses[1].json()
            else:
                assert sorted(r.status_code for r in responses) == [200, 403]
                winner = next(i for i, response in enumerate(responses) if response.status_code == 200)
                key = keys[winner]
                rejected = await client.get(f"/api/evaluations/{keys[1 - winner]}/questions")
                assert rejected.status_code == 409
                assert rejected.json() == {"statuscode": 409, "message": "El examen teórico todavía no comenzó.", "data": None}
            questions = await client.get(f"/api/evaluations/{key}/questions")
            assert questions.status_code == 200 and questions.json()["count"] == 5
            assert len({q["id"] for q in questions.json()["data"]}) == 5
            spent = await client.get(root + "/preflight")
            assert spent.status_code == 403
            assert spent.json() == {"statuscode": 403, "message": "Límite de evaluaciones gratuitas alcanzado para esta habilidad", "data": None}
    finally:
        app.dependency_overrides.pop(get_db, None)
        async with engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await engine.dispose()
