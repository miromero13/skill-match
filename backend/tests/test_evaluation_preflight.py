"""Public preflight/consent behavior in an isolated PostgreSQL schema."""
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
from app.models import Category, Skill, TeachingSkill, User, UserRole


@pytest.fixture
async def isolated_db():
    engine = create_async_engine(settings.async_database_url)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        schema = f"test_preflight_{uuid.uuid4().hex}"
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        await connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
        await connection.run_sync(Base.metadata.create_all)
        session = AsyncSession(bind=connection, expire_on_commit=False,
                               join_transaction_mode="create_savepoint")
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


@pytest.fixture
async def scenario(isolated_db):
    user = User(email=f"{uuid.uuid4()}@example.test", full_name="Member", role=UserRole.MEMBER,
                biometric_embedding="[0.1]", biometric_face_hash="enrolled-reference")
    category = Category(name="Programming", slug=str(uuid.uuid4()), is_active=True)
    isolated_db.add_all([user, category])
    await isolated_db.flush()
    skill = Skill(name="Python", slug=str(uuid.uuid4()), category_id=category.id, is_active=True)
    isolated_db.add(skill)
    await isolated_db.flush()
    offer = TeachingSkill(user_id=user.id, skill_id=skill.id, declared_level="BEGINNER",
                          years_of_experience=1, accepts_points=False)
    isolated_db.add(offer)
    await isolated_db.commit()
    token = create_access_token(subject=str(user.id), role="MEMBER")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.headers["Authorization"] = f"Bearer {token}"
        yield client, isolated_db, user, offer


def endpoint(offer, action):
    return f"/api/evaluations/skills/{offer.id}/{action}"


CONSENT = {"biometric_consent": True, "integrity_consent": True,
           "attempt_rule_accepted": True, "policy_version": "v1.0"}


@pytest.mark.asyncio
async def test_reading_and_consent_never_consume_attempt(scenario):
    client, _, _, offer = scenario
    for _ in range(2):
        response = await client.get(endpoint(offer, "preflight"))
        assert response.status_code == 200
        assert response.json()["message"] == "Preparación de evaluación recuperada exitosamente."
        assert response.json()["data"]["free_evaluations_left"] == 3
        assert response.json()["data"]["attempts_used"] == 0
    first = await client.post(endpoint(offer, "consent"), json=CONSENT)
    second = await client.post(endpoint(offer, "consent"), json=CONSENT)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert first.json()["message"] == "Consentimiento registrado. El intento aún no comenzó ni se descontó."
    assert first.json()["data"]["status"] == "PENDING_CALIBRATION"
    assert first.json()["data"]["started_at"] is None
    after = await client.get(endpoint(offer, "preflight"))
    assert after.json()["data"]["free_evaluations_left"] == 3
    assert after.json()["data"]["attempts_used"] == 0
    assert after.json()["data"]["pending_evaluation_id"] == first.json()["data"]["id"]


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["preflight", "consent"])
async def test_missing_enrollment_rejected_without_consumption(scenario, action):
    client, db, user, offer = scenario
    user.biometric_embedding = None
    await db.commit()
    response = (await client.get(endpoint(offer, action)) if action == "preflight"
                else await client.post(endpoint(offer, action), json=CONSENT))
    assert response.status_code == 400
    assert response.json() == {"statuscode": 400, "message": "Debe registrar su rostro testigo en su perfil antes de solicitar una certificación", "data": None}
    user.biometric_embedding = "[0.1]"
    await db.commit()
    check = await client.get(endpoint(offer, "preflight"))
    assert check.json()["data"]["pending_evaluation_id"] is None
    assert check.json()["data"]["free_evaluations_left"] == 3


@pytest.mark.asyncio
async def test_foreign_offer_is_hidden(scenario):
    client, db, user, offer = scenario
    original_auth = client.headers["Authorization"]
    other = User(email=f"{uuid.uuid4()}@example.test", full_name="Other", role=UserRole.MEMBER)
    db.add(other)
    await db.commit()
    client.headers["Authorization"] = f"Bearer {create_access_token(subject=str(other.id), role='MEMBER')}"
    for response in [await client.get(endpoint(offer, "preflight")),
                     await client.post(endpoint(offer, "consent"), json=CONSENT)]:
        assert response.status_code == 404
        assert response.json() == {"statuscode": 404, "message": "Recurso no encontrado", "data": None}
    client.headers["Authorization"] = original_auth
    check = (await client.get(endpoint(offer, "preflight"))).json()["data"]
    assert check["pending_evaluation_id"] is None and check["free_evaluations_left"] == 3


@pytest.mark.asyncio
async def test_unaccepted_consent_does_not_create_or_consume(scenario):
    client, _, _, offer = scenario
    response = await client.post(endpoint(offer, "consent"), json={**CONSENT, "integrity_consent": False})
    assert response.status_code == 422
    assert set(response.json()) == {"statuscode", "message", "data"}
    assert response.json()["data"] is None
    check = (await client.get(endpoint(offer, "preflight"))).json()["data"]
    assert check["pending_evaluation_id"] is None
    assert check["free_evaluations_left"] == 3


@pytest.mark.asyncio
async def test_started_attempt_remains_spent_after_abandonment(scenario):
    from app.models.evaluation import Evaluation
    client, db, user, offer = scenario
    db.add(Evaluation(user_id=user.id, skill_id=offer.skill_id, teaching_skill_id=offer.id,
                      status="ABANDONED", started_at=datetime.now(timezone.utc),
                      biometric_consent_at=datetime.now(timezone.utc), policy_version="v1.0",
                      ip_address="127.0.0.1", user_agent="test"))
    await db.commit()
    for action in ("preflight", "consent"):
        response = (await client.get(endpoint(offer, action)) if action == "preflight"
                    else await client.post(endpoint(offer, action), json=CONSENT))
        assert response.status_code == 403
        assert response.json() == {"statuscode": 403, "message": "Límite de evaluaciones gratuitas alcanzado para esta habilidad", "data": None}


@pytest.mark.asyncio
async def test_anonymous_cannot_read_or_consent(scenario):
    client, _, _, offer = scenario
    original_auth = client.headers.pop("Authorization")
    for response in [await client.get(endpoint(offer, "preflight")),
                     await client.post(endpoint(offer, "consent"), json=CONSENT)]:
        assert response.status_code == 401
        assert response.json()["data"] is None
    client.headers["Authorization"] = original_auth
    check = (await client.get(endpoint(offer, "preflight"))).json()["data"]
    assert check["pending_evaluation_id"] is None and check["free_evaluations_left"] == 3


@pytest.mark.asyncio
async def test_three_started_skills_exhaust_global_quota(scenario):
    from app.models.evaluation import Evaluation
    client, db, user, offer = scenario
    for _ in range(3):
        skill = Skill(name=f"Another skill {uuid.uuid4()}", slug=str(uuid.uuid4()),
                      category_id=(await db.get(Skill, offer.skill_id)).category_id, is_active=True)
        db.add(skill)
        await db.flush()
        db.add(Evaluation(user_id=user.id, skill_id=skill.id, status="COMPLETED",
                          biometric_consent_at=datetime.now(timezone.utc),
                          started_at=datetime.now(timezone.utc), policy_version="v1.0",
                          ip_address="127.0.0.1", user_agent="test"))
    await db.commit()
    for action in ("preflight", "consent"):
        response = (await client.get(endpoint(offer, action)) if action == "preflight"
                    else await client.post(endpoint(offer, action), json=CONSENT))
        assert response.status_code == 403
        assert response.json() == {"statuscode": 403, "message": "Límite de evaluaciones gratuitas alcanzado para esta habilidad", "data": None}


@pytest.mark.asyncio
async def test_outdated_policy_does_not_create_or_consume(scenario):
    client, _, _, offer = scenario
    response = await client.post(endpoint(offer, "consent"), json={**CONSENT, "policy_version": "old"})
    assert response.status_code == 409
    assert response.json() == {"statuscode": 409, "message": "Las condiciones cambiaron. Volvé a leerlas antes de aceptar.", "data": None}
    check = (await client.get(endpoint(offer, "preflight"))).json()["data"]
    assert check["pending_evaluation_id"] is None and check["free_evaluations_left"] == 3
