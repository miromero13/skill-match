import uuid
from typing import AsyncGenerator
import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.db.session import get_db
from app.main import app
from app.models.catalog import Category, Skill
from app.models.teaching_skill import TeachingSkill
from app.models.user import User, UserRole


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provee una sesión asíncrona real contra PostgreSQL aislada con savepoint."""
    engine = create_async_engine(settings.async_database_url, pool_pre_ping=True)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        async def override_db():
            yield session

        app.dependency_overrides[get_db] = override_db
        try:
            yield session
        finally:
            app.dependency_overrides.pop(get_db, None)
            await session.close()
            await transaction.rollback()
    await engine.dispose()


@pytest.fixture
async def seed_member(db_session: AsyncSession) -> User:
    user = User(
        email=f"instructor_{uuid.uuid4().hex[:8]}@skillmatch.local",
        full_name="Instructor Prueba",
        role=UserRole.MEMBER,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def seed_catalog_skill(db_session: AsyncSession) -> Skill:
    category = Category(
        name=f"Categoría Test {uuid.uuid4().hex[:6]}",
        slug=f"cat-test-{uuid.uuid4().hex[:6]}",
        description="Categoría para pruebas",
        is_active=True,
    )
    db_session.add(category)
    await db_session.flush()

    skill = Skill(
        name=f"Habilidad Test {uuid.uuid4().hex[:6]}",
        slug=f"skill-test-{uuid.uuid4().hex[:6]}",
        category_id=category.id,
        description="Descripción de prueba",
        is_active=True,
    )
    db_session.add(skill)
    await db_session.commit()
    await db_session.refresh(skill)
    return skill


@pytest.mark.asyncio
async def test_create_teaching_skill_success(
    client: AsyncClient,
    db_session: AsyncSession,
    seed_member: User,
    seed_catalog_skill: Skill,
):
    """Verifica el alta exitosa de una habilidad ofrecida (HU-14)."""
    payload = {
        "skill_id": str(seed_catalog_skill.id),
        "declared_level": "INTERMEDIATE",
        "years_of_experience": 4,
        "description": "4 años desarrollando software",
        "accepts_points": True,
        "hourly_points_rate": 25,
    }
    response = await client.post(
        "/api/users/me/teaching-skills",
        json=payload,
        headers={"X-User-Id": str(seed_member.id)},
    )
    assert response.status_code in (200, 201)
    body = response.json()
    assert body["statuscode"] in (200, 201)
    assert body["data"]["years_of_experience"] == 4
    assert body["data"]["declared_level"] == "INTERMEDIATE"
    assert body["data"]["status"] == "DECLARADA"
    assert body["data"]["hourly_points_rate"] == 25


@pytest.mark.asyncio
async def test_teaching_skill_invalid_experience(
    client: AsyncClient,
    seed_member: User,
    seed_catalog_skill: Skill,
):
    """Verifica que años de experiencia mayores a 60 sean rechazados."""
    payload = {
        "skill_id": str(seed_catalog_skill.id),
        "declared_level": "ADVANCED",
        "years_of_experience": 65,
        "accepts_points": False,
    }
    response = await client.post(
        "/api/users/me/teaching-skills",
        json=payload,
        headers={"X-User-Id": str(seed_member.id)},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_teaching_skill_rate_points_consistency(
    client: AsyncClient,
    seed_member: User,
    seed_catalog_skill: Skill,
):
    """Verifica que accepts_points=True requiera tarifa obligatoria."""
    payload = {
        "skill_id": str(seed_catalog_skill.id),
        "declared_level": "BEGINNER",
        "years_of_experience": 2,
        "accepts_points": True,
        "hourly_points_rate": None,
    }
    response = await client.post(
        "/api/users/me/teaching-skills",
        json=payload,
        headers={"X-User-Id": str(seed_member.id)},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_teaching_skill_rejects_negative_rate(
    client: AsyncClient,
    seed_member: User,
    seed_catalog_skill: Skill,
):
    """Verifica que tarifas negativas sean rechazadas con 422 (HU-14)."""
    payload = {
        "skill_id": str(seed_catalog_skill.id),
        "declared_level": "INTERMEDIATE",
        "years_of_experience": 3,
        "accepts_points": True,
        "hourly_points_rate": -15,
    }
    response = await client.post(
        "/api/users/me/teaching-skills",
        json=payload,
        headers={"X-User-Id": str(seed_member.id)},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_database_constraint_rejects_negative_rate(
    db_session: AsyncSession,
    seed_member: User,
    seed_catalog_skill: Skill,
):
    """Verifica que la restricción ck_teaching_rate en PostgreSQL rechace tarifas negativas a nivel DB."""
    invalid_offer = TeachingSkill(
        user_id=seed_member.id,
        skill_id=seed_catalog_skill.id,
        declared_level="INTERMEDIATE",
        years_of_experience=3,
        accepts_points=True,
        hourly_points_rate=-10,
        status="DECLARADA",
    )
    db_session.add(invalid_offer)
    with pytest.raises(Exception) as exc_info:
        await db_session.flush()
    assert "ck_teaching_rate" in str(exc_info.value)
