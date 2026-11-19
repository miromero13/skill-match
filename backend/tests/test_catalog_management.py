import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.deps import get_current_admin_user
from app.db.session import get_db
from app.main import app
from app.models.user import User, UserRole
from auth_catalog_fixtures import isolated_db  # noqa: F401
from test_catalog_hierarchy import catalog_client  # noqa: F401


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
    category = await client.post("/api/admin/catalog/categories", json={"name": "Programación"})
    response = await client.post("/api/admin/catalog/skills", json={
        "category_id": category.json()["data"]["id"], "name": "Python avanzado"
    })
    assert response.status_code == 201
    levels = response.json()["data"]["levels"]
    assert [level["name"] for level in levels] == [
        "Principiante", "Elemental", "Intermedio", "Avanzado", "Master Pedagogo"
    ]
    assert all(level["rubric"] is not None for level in levels)


@pytest.mark.asyncio
async def test_admin_can_update_skill_rubric_and_toggle_ready(client):
    category = await client.post("/api/admin/catalog/categories", json={"name": "Programación"})
    category_id = category.json()["data"]["id"]
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
    category = await client.post("/api/admin/catalog/categories", json={"name": "Programación"})
    category_id = category.json()["data"]["id"]
    await client.post("/api/admin/catalog/skills", json={
        "category_id": str(category_id), "name": "Algoritmos y Estructuras"
    })
    response = await client.get("/api/admin/catalog/skills")
    assert response.status_code == 200
    assert response.json()["statuscode"] == 200
    assert response.json()["count"] >= 1
    assert len(response.json()["data"][0]["levels"]) >= 1


@pytest.mark.asyncio
async def test_admin_can_create_categories_outside_original_three(catalog_client):
    ctx = catalog_client
    res = await ctx.client.post("/api/admin/catalog/categories", headers=ctx.admin, json={"name": "Arte y Pintura"})
    assert res.status_code == 201
    assert res.json()["statuscode"] == 201
    assert res.json()["message"] == "Categoría creada exitosamente."
    item = res.json()["data"]
    assert item["name"] == "Arte y Pintura" and item["parent_id"] is None
    listed = (await ctx.client.get("/api/admin/catalog/categories", headers=ctx.admin)).json()
    assert listed["count"] == 1 and listed["data"][0]["id"] == item["id"]


@pytest.mark.asyncio
async def test_admin_can_update_and_soft_delete_category_without_erasing_it(catalog_client):
    ctx = catalog_client
    created = await ctx.client.post("/api/admin/catalog/categories", headers=ctx.admin, json={"name": "Área temporal"})
    assert created.status_code == 201
    cat_id = created.json()["data"]["id"]
    update_res = await ctx.client.put(f"/api/admin/catalog/categories/{cat_id}", headers=ctx.admin, json={"name": "Área actualizada"})
    assert update_res.status_code == 200
    assert update_res.json()["message"] == "Categoría actualizada exitosamente."
    assert update_res.json()["data"]["id"] == cat_id
    assert update_res.json()["data"]["name"] == "Área actualizada"

    delete_res = await ctx.client.delete(f"/api/admin/catalog/categories/{cat_id}", headers=ctx.admin)
    assert delete_res.status_code == 200
    assert delete_res.json()["statuscode"] == 200
    assert delete_res.json()["message"] == "Categoría desactivada exitosamente."
    assert delete_res.json()["data"] is None
    listed = (await ctx.client.get("/api/admin/catalog/categories", headers=ctx.admin)).json()
    assert listed["count"] == 1
    assert listed["data"][0]["id"] == cat_id and listed["data"][0]["name"] == "Área actualizada"
    assert listed["data"][0]["is_active"] is False

    # Missing resources still reject both mutations and leave the catalog unchanged.
    missing = f"/api/admin/catalog/categories/{uuid.uuid4()}"
    for response in (
        await ctx.client.put(missing, headers=ctx.admin, json={"name": "Otra"}),
        await ctx.client.delete(missing, headers=ctx.admin),
    ):
        assert response.status_code == 404
        assert response.json() == {"statuscode": 404, "message": "Categoría no encontrada", "data": None}
    assert (await ctx.client.get("/api/admin/catalog/categories", headers=ctx.admin)).json() == listed

