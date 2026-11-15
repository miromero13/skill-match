import uuid
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.deps import get_current_user
from app.db.session import get_db
from app.main import app
from app.models.catalog import Category, Skill
from app.models.user import User, UserRole
from app.models.user_learning_skill import UserLearningSkill, UrgencyLevel
from app.core.security import create_access_token


class MockLearningSession:
    def __init__(self, current_user: User):
        self.current_user = current_user
        self.categories: list[Category] = []
        self.skills: list[Skill] = []
        self.learning_skills: list[UserLearningSkill] = []

    async def execute(self, statement, *args, **kwargs):
        desc = statement.column_descriptions[0]
        entity = desc.get("entity")

        compiled = statement.compile()
        params = compiled.params

        class Result:
            def __init__(self, data):
                self.data = data

            def scalar_one_or_none(self):
                return self.data[-1] if self.data else None

            def scalar_one(self):
                return self.data[-1]

            def scalars(self):
                class Scalars:
                    def __init__(self, data):
                        self.data = data

                    def all(self):
                        return self.data

                    def unique(self):
                        return self

                return Scalars(self.data)

        if entity is Skill:
            skill_id = None
            for k, v in params.items():
                if "id" in k:
                    skill_id = v
            matched = [s for s in self.skills if skill_id is None or s.id == skill_id]
            return Result(matched)

        if entity is UserLearningSkill:
            u_id = params.get("user_id_1") or params.get("user_id")
            s_id = params.get("skill_id_1") or params.get("skill_id")
            ls_id = params.get("id_1") or params.get("id")

            matched = self.learning_skills
            if u_id:
                matched = [m for m in matched if m.user_id == u_id]
            if s_id:
                matched = [m for m in matched if m.skill_id == s_id]
            if ls_id:
                matched = [m for m in matched if m.id == ls_id]

            return Result(matched)

        return Result([])

    def add(self, item):
        from datetime import datetime, timezone
        if isinstance(item, UserLearningSkill):
            if not item.id:
                item.id = uuid.uuid4()
            if not item.created_at:
                item.created_at = datetime.now(timezone.utc)
            if not item.updated_at:
                item.updated_at = datetime.now(timezone.utc)
            for s in self.skills:
                if s.id == item.skill_id:
                    item.skill = s
                    break
            self.learning_skills.append(item)

    async def commit(self):
        pass

    async def refresh(self, item):
        pass

    async def delete(self, item):
        if item in self.learning_skills:
            self.learning_skills.remove(item)


@pytest.fixture
def mock_setup():
    user = User(
        id=uuid.uuid4(),
        email="test.member@skillmatch.io",
        full_name="Miembro de Prueba",
        role=UserRole.MEMBER,
        is_active=True,
    )

    category = Category(
        id=uuid.uuid4(),
        name="Programación",
        slug="programacion",
        is_active=True,
    )

    skill = Skill(
        id=uuid.uuid4(),
        category_id=category.id,
        name="Python y FastAPI",
        slug="python-fastapi",
        is_active=True,
    )
    skill.category = category

    session = MockLearningSession(user)
    session.categories.append(category)
    session.skills.append(skill)

    token = create_access_token(user.id, user.role.value)
    headers = {"Authorization": f"Bearer {token}"}

    async def override_db():
        yield session

    async def override_user():
        return user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user

    yield {
        "user": user,
        "category": category,
        "skill": skill,
        "session": session,
        "headers": headers,
    }

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_unauthenticated_request_fails():
    app.dependency_overrides.clear()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/users/me/learning-skills")
        assert resp.status_code == 401
        body = resp.json()
        assert body["statuscode"] == 401


@pytest.mark.asyncio
async def test_list_learning_skills_empty(mock_setup):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/users/me/learning-skills", headers=mock_setup["headers"])
        assert resp.status_code == 200
        body = resp.json()
        assert body["statuscode"] == 200
        assert body["data"] == []
        assert body["count"] == 0


@pytest.mark.asyncio
async def test_add_learning_skill_success(mock_setup):
    transport = ASGITransport(app=app)
    skill = mock_setup["skill"]
    payload = {
        "skill_id": str(skill.id),
        "current_level": 1,
        "target_level": 4,
        "urgency": "HIGH",
        "notes": "Quiero aprender para crear microservicios.",
    }
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/users/me/learning-skills",
            json=payload,
            headers=mock_setup["headers"],
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["statuscode"] == 201
        assert body["data"]["skill_id"] == str(skill.id)
        assert body["data"]["current_level"] == 1
        assert body["data"]["target_level"] == 4
        assert body["data"]["urgency"] == "HIGH"
        assert body["data"]["notes"] == payload["notes"]
        assert body["data"]["skill"]["name"] == "Python y FastAPI"


@pytest.mark.asyncio
async def test_add_learning_skill_target_lower_than_current_fails(mock_setup):
    transport = ASGITransport(app=app)
    skill = mock_setup["skill"]
    payload = {
        "skill_id": str(skill.id),
        "current_level": 4,
        "target_level": 2,  # Inválido: meta menor a actual
        "urgency": "MEDIUM",
    }
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/users/me/learning-skills",
            json=payload,
            headers=mock_setup["headers"],
        )
        assert resp.status_code == 422
        body = resp.json()
        assert body["statuscode"] == 422


@pytest.mark.asyncio
async def test_add_learning_skill_duplicate_fails(mock_setup):
    transport = ASGITransport(app=app)
    skill = mock_setup["skill"]
    session = mock_setup["session"]

    # Agregar previamente una vez
    existing = UserLearningSkill(
        user_id=mock_setup["user"].id,
        skill_id=skill.id,
        current_level=1,
        target_level=3,
        urgency=UrgencyLevel.LOW,
    )
    session.add(existing)

    payload = {
        "skill_id": str(skill.id),
        "current_level": 1,
        "target_level": 3,
        "urgency": "HIGH",
    }
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/users/me/learning-skills",
            json=payload,
            headers=mock_setup["headers"],
        )
        assert resp.status_code == 409
        body = resp.json()
        assert body["statuscode"] == 409
        assert "Ya tienes" in body["message"]


@pytest.mark.asyncio
async def test_update_learning_skill_success(mock_setup):
    transport = ASGITransport(app=app)
    skill = mock_setup["skill"]
    session = mock_setup["session"]

    existing = UserLearningSkill(
        user_id=mock_setup["user"].id,
        skill_id=skill.id,
        current_level=1,
        target_level=3,
        urgency=UrgencyLevel.LOW,
    )
    session.add(existing)

    update_payload = {
        "target_level": 5,
        "urgency": "HIGH",
        "notes": "Actualizado para proyecto de fin de año.",
    }
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.put(
            f"/api/users/me/learning-skills/{existing.id}",
            json=update_payload,
            headers=mock_setup["headers"],
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["statuscode"] == 200
        assert body["data"]["target_level"] == 5
        assert body["data"]["urgency"] == "HIGH"
        assert body["data"]["notes"] == update_payload["notes"]


@pytest.mark.asyncio
async def test_delete_learning_skill_success(mock_setup):
    transport = ASGITransport(app=app)
    skill = mock_setup["skill"]
    session = mock_setup["session"]

    existing = UserLearningSkill(
        user_id=mock_setup["user"].id,
        skill_id=skill.id,
        current_level=1,
        target_level=3,
        urgency=UrgencyLevel.LOW,
    )
    session.add(existing)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.delete(
            f"/api/users/me/learning-skills/{existing.id}",
            headers=mock_setup["headers"],
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["statuscode"] == 200
        assert "removida" in body["message"]

        # Verificar que la lista queda vacía
        list_resp = await client.get("/api/users/me/learning-skills", headers=mock_setup["headers"])
        assert list_resp.json()["data"] == []
