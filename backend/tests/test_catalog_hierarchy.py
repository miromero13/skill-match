"""HU-12 acceptance through existing public/admin HTTP routes, in an isolated schema."""
from types import SimpleNamespace
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token
from app.main import app
from app.models.user import User
from auth_catalog_fixtures import isolated_db


@pytest.fixture
async def catalog_client(isolated_db):
    users = [User(id=uuid.uuid4(), email=f"{role.lower()}@example.com", full_name=role, role=role,
                  is_active=True, is_locked=False) for role in ("ADMIN", "MEMBER")]
    isolated_db.add_all(users)
    await isolated_db.commit()
    headers = [{"Authorization": f"Bearer {create_access_token(str(user.id), user.role)}"} for user in users]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        yield SimpleNamespace(client=client, admin=headers[0], member=headers[1])


async def category(ctx, name, parent_id=None):
    response = await ctx.client.post("/api/admin/catalog/categories", headers=ctx.admin, json={"name": name, "parent_id": parent_id})
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def skill(ctx, category_id, name="Python"):
    response = await ctx.client.post("/api/admin/catalog/skills", headers=ctx.admin, json={"category_id": category_id, "name": name})
    assert response.status_code == 201, response.text
    return response.json()["data"]


@pytest.mark.asyncio
async def test_hierarchy_roundtrips_and_rejects_cycles_without_mutation(catalog_client):
    ctx = catalog_client
    root = await category(ctx, "Programación")
    child = await category(ctx, "Lenguajes", root["id"])
    assert root["parent_id"] is None
    assert child["parent_id"] == root["id"]
    response = await ctx.client.put(f'/api/admin/catalog/categories/{root["id"]}', headers=ctx.admin, json={"parent_id": child["id"]})
    assert response.status_code == 400
    assert response.json()["message"] == "La jerarquía de categorías no puede contener ciclos."
    assert response.json()["data"] is None
    listed = (await ctx.client.get("/api/admin/catalog/categories", headers=ctx.admin)).json()
    assert listed["count"] == 2
    assert next(item for item in listed["data"] if item["id"] == root["id"])["parent_id"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["  python  ", "PYTHON", "Ｐｙｔｈｏｎ"])
async def test_normalized_skill_duplicates_rejected_but_same_name_in_other_category_allowed(catalog_client, name):
    ctx = catalog_client
    root = await category(ctx, "Programación")
    original = await skill(ctx, root["id"])
    rejected = await ctx.client.post("/api/admin/catalog/skills", headers=ctx.admin, json={"category_id": root["id"], "name": name})
    assert rejected.status_code == 409
    assert rejected.json()["data"] is None
    listed = (await ctx.client.get("/api/admin/catalog/skills", headers=ctx.admin)).json()
    assert listed["count"] == 1
    assert listed["data"][0]["id"] == original["id"]
    assert listed["data"][0]["name"] == "Python"
    other = await category(ctx, "Otra área")
    allowed = await skill(ctx, other["id"])
    assert allowed["slug"] != original["slug"]


@pytest.mark.asyncio
async def test_normalized_sibling_categories_are_unique_and_updates_preserve_original_on_rejection(catalog_client):
    ctx = catalog_client
    music = await category(ctx, "Música")
    duplicate = await ctx.client.post("/api/admin/catalog/categories", headers=ctx.admin, json={"name": "  MUSICA  "})
    assert duplicate.status_code == 409
    assert duplicate.json()["data"] is None
    first = await category(ctx, "Guitarra", music["id"])
    second = await category(ctx, "Piano", music["id"])
    rejected = await ctx.client.put(f'/api/admin/catalog/categories/{second["id"]}', headers=ctx.admin, json={"name": " GUITARRA "})
    assert rejected.status_code == 409
    listed = (await ctx.client.get("/api/admin/catalog/categories", headers=ctx.admin)).json()
    assert listed["count"] == 3
    assert next(item for item in listed["data"] if item["id"] == second["id"])["name"] == "Piano"
    other = await category(ctx, "Otras disciplinas")
    allowed = await category(ctx, "Guitarra", other["id"])
    assert allowed["id"] != first["id"]


@pytest.mark.asyncio
@pytest.mark.parametrize("resource,payload", [("categories", {"name": "   "}), ("categories", {"name": "Child", "parent_id": str(uuid.uuid4())})])
async def test_rejected_category_input_leaves_catalog_empty(catalog_client, resource, payload):
    ctx = catalog_client
    response = await ctx.client.post(f"/api/admin/catalog/{resource}", headers=ctx.admin, json=payload)
    assert response.status_code == (422 if payload["name"].isspace() else 404)
    assert response.json()["data"] is None
    listed = (await ctx.client.get("/api/admin/catalog/categories", headers=ctx.admin)).json()
    assert listed["data"] == []
    assert listed["count"] == 0


@pytest.mark.asyncio
async def test_public_detail_and_root_filter_include_active_descendants_only(catalog_client):
    ctx = catalog_client
    root = await category(ctx, "Programación")
    child = await category(ctx, "Lenguajes", root["id"])
    entry = await skill(ctx, child["id"])
    assert (await ctx.client.get(f'/api/skills/{entry["id"]}')).status_code == 404
    assert (await ctx.client.get("/api/skills")).json()["count"] == 0
    await ctx.client.patch(f'/api/admin/catalog/skills/{entry["id"]}/status', headers=ctx.admin, json={"is_active": True})
    detail = await ctx.client.get(f'/api/skills/{entry["id"]}')
    assert detail.status_code == 200
    assert detail.json()["data"]["id"] == entry["id"]
    assert len(detail.json()["data"]["levels"]) == 5
    listed = (await ctx.client.get("/api/skills", params={"category_id": root["id"]})).json()
    assert listed["count"] == 1
    assert listed["data"][0]["id"] == entry["id"]
    await ctx.client.delete(f'/api/admin/catalog/categories/{root["id"]}', headers=ctx.admin)
    assert (await ctx.client.get("/api/categories")).json()["data"] == []
    assert (await ctx.client.get("/api/skills")).json()["count"] == 0
    assert (await ctx.client.get(f'/api/skills/{entry["id"]}')).status_code == 404
    assert (await ctx.client.get("/api/admin/catalog/categories", headers=ctx.admin)).json()["count"] == 2
    assert (await ctx.client.get(f'/api/admin/catalog/skills/{entry["id"]}', headers=ctx.admin)).status_code == 200


@pytest.mark.asyncio
async def test_linked_delete_is_rejected_but_deactivation_preserves_learning_demand(catalog_client):
    ctx = catalog_client
    root = await category(ctx, "Programación")
    entry = await skill(ctx, root["id"])
    await ctx.client.patch(f'/api/admin/catalog/skills/{entry["id"]}/status', headers=ctx.admin, json={"is_active": True})
    linked = await ctx.client.post("/api/users/me/learning-skills", headers=ctx.member, json={"skill_id": entry["id"], "current_level": 1, "target_level": 3})
    assert linked.status_code == 201, linked.text
    before = (await ctx.client.get("/api/users/me/learning-skills", headers=ctx.member)).json()
    rejected = await ctx.client.delete(f'/api/admin/catalog/skills/{entry["id"]}', headers=ctx.admin)
    assert rejected.status_code == 409
    assert rejected.json()["data"] is None
    assert (await ctx.client.get(f'/api/skills/{entry["id"]}')).status_code == 200
    disabled = await ctx.client.patch(f'/api/admin/catalog/skills/{entry["id"]}/status', headers=ctx.admin, json={"is_active": False})
    assert disabled.status_code == 200
    assert (await ctx.client.get(f'/api/skills/{entry["id"]}')).status_code == 404
    after = (await ctx.client.get("/api/users/me/learning-skills", headers=ctx.member)).json()
    assert after == before


@pytest.mark.asyncio
async def test_unlinked_delete_is_logical_and_preserves_levels(catalog_client):
    ctx = catalog_client
    root = await category(ctx, "Programación")
    entry = await skill(ctx, root["id"])
    response = await ctx.client.delete(f'/api/admin/catalog/skills/{entry["id"]}', headers=ctx.admin)
    assert response.status_code == 200
    assert response.json()["data"] is None
    detail = await ctx.client.get(f'/api/admin/catalog/skills/{entry["id"]}', headers=ctx.admin)
    assert detail.status_code == 200
    assert detail.json()["data"]["is_active"] is False
    assert detail.json()["data"]["levels"] == entry["levels"]
    assert (await ctx.client.get("/api/admin/catalog/skills", headers=ctx.admin)).json()["count"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("headers", [None, "member"])
async def test_catalog_mutations_remain_hidden_from_anonymous_and_members(catalog_client, headers):
    ctx = catalog_client
    response = await ctx.client.post("/api/admin/catalog/categories", headers=ctx.member if headers else {}, json={"name": "Forbidden"})
    assert response.status_code == 404
    assert response.json()["message"] == "Recurso no encontrado"
    assert response.json()["data"] is None
    assert (await ctx.client.get("/api/admin/catalog/categories", headers=ctx.admin)).json()["count"] == 0
