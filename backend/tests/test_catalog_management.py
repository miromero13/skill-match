import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.deps import get_current_admin_user
from app.db.session import get_db
from app.main import app
from app.models.user import User, UserRole


class CatalogTestSession:
    def __init__(self):
        self.items = []
        self.latest = None

    async def execute(self, statement, *args, **kwargs):
        from app.models.catalog import Category, ChallengeType, Skill
        desc = statement.column_descriptions[0]
        entity = desc.get("entity")
        expr = desc.get("expr")
        is_entity_query = expr is entity and entity in (Category, ChallengeType, Skill)

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

        if not is_entity_query:
            # Slug probe or column query: check if slug exists
            slug_val = None
            exclude_id_val = None
            for k, v in params.items():
                if "slug" in k:
                    slug_val = v
                elif "id" in k:
                    exclude_id_val = v
            matching = [
                item for item in self.items
                if isinstance(item, entity)
                and (slug_val is None or getattr(item, "slug", None) == slug_val)
                and (exclude_id_val is None or getattr(item, "id", None) != exclude_id_val)
            ]
            return Result(matching)

        # Entity query
        items = [item for item in self.items if isinstance(item, entity)]
        # Filter by id if present in params
        id_filter = None
        for k, v in params.items():
            if "id" in k:
                id_filter = v
                break
        if id_filter is not None:
            items = [item for item in items if getattr(item, "id", None) == id_filter]

        return Result(items or ([self.latest] if self.latest and isinstance(self.latest, entity) else []))

    def add(self, instance):
        if getattr(instance, "id", None) is None:
            instance.id = uuid.uuid4()
        self.latest = instance
        self.items.append(instance)

    async def get(self, model, item_id):
        return next((item for item in self.items if isinstance(item, model) and item.id == item_id), None)

    async def commit(self):
        pass

    async def refresh(self, instance):
        pass

    async def flush(self):
        pass

    async def delete(self, instance):
        if instance in self.items:
            self.items.remove(instance)


@pytest.fixture
async def client():
    admin = User(
        id=uuid.uuid4(), email="admin@example.com", full_name="Admin",
        role=UserRole.ADMIN, is_active=True, is_locked=False,
    )

    session = CatalogTestSession()

    async def override_db():
        yield session

    async def override_admin():
        return admin

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_admin_user] = override_admin
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_catalog_rejects_non_admin_with_obfuscated_404():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/admin/catalog/categories")
    assert response.status_code == 404
    assert response.json()["message"] == "Recurso no encontrado"


@pytest.mark.asyncio
async def test_admin_can_create_and_list_category(client):
    created = await client.post("/api/admin/catalog/categories", json={"name": "Programación", "description": "Código"})
    listed = await client.get("/api/admin/catalog/categories")
    assert created.status_code == 201
    assert created.json()["data"]["slug"] == "programacion"
    assert listed.status_code == 200
    assert listed.json()["statuscode"] == 200


@pytest.mark.asyncio
async def test_admin_can_create_challenge_type_and_list(client):
    created = await client.post("/api/admin/catalog/challenge-types", json={
        "name": "Retos de código", "code": "CODE", "evaluation_modality": "CODE"
    })
    listed = await client.get("/api/admin/catalog/challenge-types")
    assert created.status_code == 201
    assert created.json()["data"]["code"] == "CODE"
    assert listed.status_code == 200


@pytest.mark.asyncio
async def test_admin_skill_creation_provisions_canonical_levels_and_rubrics(client):
    response = await client.post("/api/admin/catalog/skills", json={
        "category_id": str(uuid.uuid4()), "name": "Python avanzado"
    })
    assert response.status_code == 201
    levels = response.json()["data"]["levels"]
    assert [level["name"] for level in levels] == [
        "Principiante", "Elemental", "Intermedio", "Avanzado", "Master Pedagogo"
    ]
    assert all(level["rubric"] is not None for level in levels)


@pytest.mark.asyncio
async def test_admin_can_update_skill_rubric_and_toggle_ready(client):
    category_id = uuid.uuid4()
    initial = await client.post("/api/admin/catalog/skills", json={
        "category_id": str(category_id), "name": "Python avanzado"
    })
    skill_id = initial.json()["data"]["id"]
    response = await client.put(f"/api/admin/catalog/skills/{skill_id}", json={
        "category_id": str(category_id), "name": "Python avanzado",
        "min_approval_threshold": 85, "is_ready_to_publish": True, "is_active": False,
        "levels": [{"level_number": 1, "name": "Principiante", "rubric": {
            "min_score": 75, "criteria": [{"name": "Sintaxis", "weight": 1, "description": "Correcta"}]
        }}]
    })
    assert response.status_code == 200
    assert response.json()["data"]["levels"][0]["rubric"]["criteria"][0]["name"] == "Sintaxis"
    ready = await client.patch(f"/api/admin/catalog/skills/{skill_id}/ready", json={"is_ready_to_publish": False})
    assert ready.status_code == 200
    assert ready.json()["data"]["is_ready_to_publish"] is False


@pytest.mark.asyncio
async def test_admin_can_list_skills(client):
    category_id = uuid.uuid4()
    await client.post("/api/admin/catalog/skills", json={
        "category_id": str(category_id), "name": "Algoritmos y Estructuras"
    })
    response = await client.get("/api/admin/catalog/skills")
    assert response.status_code == 200
    assert response.json()["statuscode"] == 200
    assert response.json()["count"] >= 1
    assert len(response.json()["data"][0]["levels"]) >= 1
