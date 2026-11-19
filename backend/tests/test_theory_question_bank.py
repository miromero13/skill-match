"""Exercise the administrative bank through HTTP in disposable test state."""
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from auth_catalog_fixtures import isolated_db
from app.core.security import create_access_token
from app.main import app
from app.models import Category, Skill, SkillLevel, User, UserRole

URL = "/api/admin/theory/questions"
CREATED = "Borrador de pregunta creado exitosamente."
LISTED = "Preguntas teóricas recuperadas exitosamente."
FOUND = "Pregunta teórica recuperada exitosamente."


@pytest.fixture
async def bank(isolated_db):
    admin = User(email=f"{uuid.uuid4()}@example.test", full_name="Test Admin", role=UserRole.ADMIN)
    member = User(email=f"{uuid.uuid4()}@example.test", full_name="Test Member", role=UserRole.MEMBER)
    category = Category(name="Theory", slug=str(uuid.uuid4()))
    isolated_db.add_all([admin, member, category])
    await isolated_db.flush()
    skill = Skill(name="Python", slug=str(uuid.uuid4()), category_id=category.id)
    isolated_db.add(skill)
    await isolated_db.flush()
    isolated_db.add(SkillLevel(skill_id=skill.id, level_number=1, name="Principiante"))
    await isolated_db.commit()
    admin_auth = f"Bearer {create_access_token(subject=str(admin.id), role='ADMIN')}"
    member_auth = f"Bearer {create_access_token(subject=str(member.id), role='MEMBER')}"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test",
                           headers={"Authorization": admin_auth}) as client:
        yield client, str(skill.id), admin_auth, member_auth


def draft(skill_id, **changes):
    return {"skill_id": skill_id, "level_number": 1, "prompt": "  Explain mutability.  ", **changes}


@pytest.mark.asyncio
async def test_create_list_and_read_draft_by_skill_and_level(bank):
    client, skill_id, _, _ = bank
    empty = await client.get(URL)
    assert empty.status_code == 200
    assert empty.json() == {"statuscode": 200, "message": LISTED, "data": [], "count": 0}
    response = await client.post(URL, json=draft(skill_id))
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"statuscode", "message", "data"}
    assert body["statuscode"] == 201 and body["message"] == CREATED
    item = body["data"]
    assert uuid.UUID(item["id"]) and item["version"] == 1
    assert item["skill_id"] == skill_id and item["level_number"] == 1
    assert item["status"] == "DRAFT"
    assert item["content"] == {"kind": "OPEN", "prompt": "Explain mutability.", "choices": [],
                               "correct_choice": None, "reference_answer": "", "criteria": [],
                               "time_limit_seconds": 90, "max_score": 20}
    listed = await client.get(URL, params={"skill_id": skill_id, "level_number": 1, "limit": 1})
    assert listed.status_code == 200
    assert listed.json() == {"statuscode": 200, "message": LISTED, "data": [item], "count": 1}
    read = await client.get(f"{URL}/{item['id']}")
    assert read.status_code == 200
    assert read.json() == {"statuscode": 200, "message": FOUND, "data": item}
    for params in [{"skill_id": str(uuid.uuid4())}, {"level_number": 2}, {"offset": 1}]:
        page = await client.get(URL, params=params)
        assert page.status_code == 200 and page.json()["data"] == []
        assert page.json()["count"] == (1 if "offset" in params else 0)


@pytest.mark.asyncio
@pytest.mark.parametrize("change", [{"prompt": "   "}, {"level_number": 0}, {"level_number": 6},
                                    {"time_limit_seconds": 0}, {"max_score": 0}, {"unexpected": True}])
async def test_invalid_drafts_leave_public_bank_unchanged(bank, change):
    client, skill_id, _, _ = bank
    before = (await client.get(URL)).json()
    rejected = await client.post(URL, json=draft(skill_id, **change))
    assert rejected.status_code == 422
    assert set(rejected.json()) == {"statuscode", "message", "data"}
    assert rejected.json()["statuscode"] == 422 and rejected.json()["data"] is None
    assert isinstance(rejected.json()["message"], str) and rejected.json()["message"]
    assert (await client.get(URL)).json() == before


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", ["skill", "level"])
async def test_missing_catalogue_pair_does_not_create_a_question(bank, missing):
    client, skill_id, _, _ = bank
    before = (await client.get(URL)).json()
    payload = draft(str(uuid.uuid4()) if missing == "skill" else skill_id,
                    level_number=1 if missing == "skill" else 5)
    rejected = await client.post(URL, json=payload)
    assert rejected.status_code == 404
    assert rejected.json() == {"statuscode": 404, "message": "Habilidad o nivel no encontrado", "data": None}
    assert (await client.get(URL)).json() == before
    missing_item = await client.get(f"{URL}/{uuid.uuid4()}")
    assert missing_item.status_code == 404
    assert missing_item.json() == {"statuscode": 404, "message": "Recurso no encontrado", "data": None}


@pytest.mark.asyncio
@pytest.mark.parametrize("actor", ["member", "anonymous"])
async def test_admin_bank_is_hidden_without_mutating_data(bank, actor):
    client, skill_id, admin_auth, member_auth = bank
    created = await client.post(URL, json=draft(skill_id))
    assert created.status_code == 201
    item = created.json()["data"]
    before = (await client.get(URL)).json()
    if actor == "member":
        client.headers["Authorization"] = member_auth
    else:
        client.headers.pop("Authorization")
    responses = [await client.get(URL), await client.get(f"{URL}/{item['id']}"),
                 await client.post(URL, json=draft(skill_id))]
    for response in responses:
        assert response.status_code == 404
        assert response.json() == {"statuscode": 404, "message": "Recurso no encontrado", "data": None}
    client.headers["Authorization"] = admin_auth
    assert (await client.get(URL)).json() == before
