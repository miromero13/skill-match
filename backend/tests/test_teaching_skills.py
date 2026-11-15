import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import Category, Skill
from app.models.teaching_skill import TeachingSkill
from app.models.user import User, UserRole


@pytest.fixture
async def seed_member(db_session: AsyncSession) -> User:
    user = User(
        email="instructor@skillmatch.local",
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
        description="Categoría para pruebas",
        is_active=True,
    )
    db_session.add(category)
    await db_session.flush()

    skill = Skill(
        name=f"Habilidad Test {uuid.uuid4().hex[:6]}",
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
