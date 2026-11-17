from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.db.session import async_engine, get_db
from app.main import create_application
from app.models.catalog import Category, Skill
from app.models.match import Match
from app.models.teaching_skill import TeachingSkill
from app.models.user import User, UserRole
from app.models.user_learning_skill import UserLearningSkill


@pytest.mark.asyncio
async def test_reciprocal_suggestions_and_private_details():
    suffix = uuid4().hex
    async with async_engine.connect() as connection:
        transaction = await connection.begin()
        try:
            async with AsyncSession(bind=connection, expire_on_commit=False) as db:
                category = Category(name="HU-21", slug=f"matches-{suffix}")
                members = [
                    User(email=f"{name}-{suffix}@example.com", full_name=name, role=UserRole.MEMBER)
                    for name in ("A", "B", "C")
                ]
                db.add_all([category, *members])
                await db.flush()
                python, guitar = [
                    Skill(name=name, slug=f"{name}-{suffix}", category_id=category.id, is_active=True)
                    for name in ("Python", "Guitarra")
                ]
                db.add_all([python, guitar])
                await db.flush()
                a, b, c = members
                b_interest = UserLearningSkill(user_id=b.id, skill_id=python.id)
                db.add_all([
                    TeachingSkill(user_id=user.id, skill_id=skill.id,
                                  declared_level="INTERMEDIATE", years_of_experience=2)
                    for user, skill in ((a, python), (b, guitar), (c, guitar))
                ])
                db.add_all([UserLearningSkill(user_id=a.id, skill_id=guitar.id), b_interest])
                await db.flush()

                async def override_db():
                    yield db

                app = create_application()
                app.dependency_overrides[get_db] = override_db
                headers = {
                    user.full_name: {"Authorization": f"Bearer {create_access_token(str(user.id), 'MEMBER')}"}
                    for user in members
                }
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app), base_url="http://test",
                ) as client:
                    url = "/api/matches/suggestions"
                    assert (await client.get(url)).status_code == 401
                    first = (await client.get(url, headers=headers["A"])).raise_for_status().json()
                    assert first["count"] == 1
                    item, = first["data"]
                    assert item["counterpart_name"] == "B"
                    assert item["status"] == "pending"
                    assert item["you_teach"] == ["Python"]
                    assert item["they_teach"] == ["Guitarra"]
                    reverse = (await client.get(url, headers=headers["B"])).raise_for_status().json()
                    assert reverse["data"][0]["id"] == item["id"]
                    assert reverse["data"][0]["you_teach"] == ["Guitarra"]
                    assert await db.scalar(
                        select(func.count()).select_from(Match).where(
                            Match.member_a_id.in_([a.id, b.id]), Match.member_b_id.in_([a.id, b.id])
                        )
                    ) == 1
                    detail_url = f"/api/matches/{item['id']}"
                    assert (await client.get(detail_url, headers=headers["A"])).status_code == 200
                    assert (await client.get(detail_url, headers=headers["C"])).status_code == 404
                    await db.delete(b_interest)
                    await db.flush()
                    assert (await client.get(url, headers=headers["A"])).raise_for_status().json()["count"] == 0
                    restored_interest = UserLearningSkill(user_id=b.id, skill_id=python.id)
                    db.add(restored_interest)
                    await db.flush()

                    # El descarte es personal y una propuesta del otro miembro lo reabre.
                    assert (await client.delete(detail_url, headers=headers["A"])).status_code == 200
                    assert (await client.get(url, headers=headers["A"])).json()["count"] == 0
                    assert (await client.get(url, headers=headers["B"])).json()["count"] == 1
                    messages_url = f"{detail_url}/messages"
                    assert (await client.get(messages_url, headers=headers["A"])).status_code == 409
                    starts_at = datetime.now(timezone.utc) + timedelta(days=1)
                    proposals_url = f"{detail_url}/proposals"
                    response = await client.post(
                        proposals_url, headers=headers["B"], json={"starts_at": starts_at.isoformat()},
                    )
                    assert response.status_code == 201
                    first_proposal = response.json()["data"]["id"]
                    assert (await client.get(url, headers=headers["A"])).json()["count"] == 1
                    response = await client.post(
                        proposals_url, headers=headers["A"],
                        json={"starts_at": (starts_at + timedelta(days=1)).isoformat(),
                              "replaces_proposal_id": first_proposal},
                    )
                    assert response.status_code == 201
                    second_proposal = response.json()["data"]["id"]
                    accept_url = f"{detail_url}/accept"
                    assert (await client.post(
                        accept_url, headers=headers["B"], json={"proposal_id": first_proposal},
                    )).status_code == 409
                    assert (await client.post(
                        accept_url, headers=headers["C"], json={"proposal_id": second_proposal},
                    )).status_code == 404
                    for _ in range(2):
                        response = await client.post(
                            accept_url, headers=headers["B"], json={"proposal_id": second_proposal},
                        )
                        assert response.status_code == 200
                        assert response.json()["data"]["contact_enabled"]
                    assert (await client.post(
                        messages_url, headers=headers["A"], json={"body": "Nos vemos el jueves."},
                    )).status_code == 201
                    response = await client.get(messages_url, headers=headers["B"])
                    assert response.json()["data"][0]["body"] == "Nos vemos el jueves."
                    assert (await client.get(messages_url, headers=headers["C"])).status_code == 404
                    await db.delete(restored_interest)
                    db.add(UserLearningSkill(user_id=c.id, skill_id=python.id))
                    await db.flush()
                    response = await client.get(url, headers=headers["A"])
                    choices = {match["counterpart_name"]: match for match in response.json()["data"]}
                    assert choices["B"]["status"] == "confirmed"
                    other_url = f"/api/matches/{choices['C']['id']}"
                    response = await client.post(
                        f"{other_url}/proposals", headers=headers["A"],
                        json={"starts_at": starts_at.isoformat()},
                    )
                    assert response.status_code == 201
                    response = await client.post(
                        f"{other_url}/decline", headers=headers["C"],
                        json={"proposal_id": response.json()["data"]["id"]},
                    )
                    assert response.status_code == 200
                    assert response.json()["data"]["status"] == "declined"
                    assert (await client.get(url, headers=headers["C"])).json()["count"] == 0
        finally:
            await transaction.rollback()
