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
            "min_score": 75, "criteria": [{"name": "Sintaxis", "weight": 100, "description": "Correcta"}]
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



# ---------------------------------------------------------------------------
# S1: criterion contract (key, metric_type, target) and the 100% weight rule.
# ---------------------------------------------------------------------------

def _levels(*criteria_per_level, names=("Básico", "Avanzado")):
    return [
        {"level_number": index + 1, "name": names[index], "rubric": {"min_score": 60, "criteria": list(criteria)}}
        for index, criteria in enumerate(criteria_per_level)
    ]


def _criterion(name, weight, **extra):
    return {"name": name, "weight": weight, "description": f"Descripción {name}", **extra}


async def _catalog_snapshot(ctx):
    return (await ctx.client.get("/api/admin/catalog/skills", headers=ctx.admin)).json()


@pytest.mark.asyncio
async def test_level_criteria_weights_must_sum_100_on_create(catalog_client):
    ctx = catalog_client
    category_id = (await ctx.client.post("/api/admin/catalog/categories", headers=ctx.admin, json={"name": "Deportes"})).json()["data"]["id"]
    accepted = await ctx.client.post("/api/admin/catalog/skills", headers=ctx.admin, json={
        "category_id": category_id, "name": "Dominadas",
        "levels": _levels([_criterion("Postura", 60), _criterion("Ritmo", 40)], []),
    })
    assert accepted.status_code == 201, accepted.text
    criteria = accepted.json()["data"]["levels"][0]["rubric"]["criteria"]
    assert [c["weight"] for c in criteria] == [60, 40]
    for criterion in criteria:
        assert set(criterion) >= {"key", "name", "weight", "description", "metric_type", "target"}
        assert criterion["key"] and criterion["metric_type"] == "REFERENCE_REPLICATION" and criterion["target"] is None
    assert len({c["key"] for c in criteria}) == 2
    assert accepted.json()["data"]["levels"][1]["rubric"]["criteria"] == []

    before = await _catalog_snapshot(ctx)
    rejected = await ctx.client.post("/api/admin/catalog/skills", headers=ctx.admin, json={
        "category_id": category_id, "name": "Pases",
        "levels": _levels([_criterion("Precisión", 50), _criterion("Potencia", 40)]),
    })
    assert rejected.status_code == 400
    assert rejected.json() == {
        "statuscode": 400,
        "message": "Los porcentajes de los criterios del nivel «Básico» deben sumar 100% (actual: 90%).",
        "data": None,
    }
    assert await _catalog_snapshot(ctx) == before


@pytest.mark.asyncio
async def test_weight_rule_on_update_rejects_without_changing_stored_skill(catalog_client):
    ctx = catalog_client
    category_id = (await ctx.client.post("/api/admin/catalog/categories", headers=ctx.admin, json={"name": "Deportes"})).json()["data"]["id"]
    created = (await ctx.client.post("/api/admin/catalog/skills", headers=ctx.admin, json={
        "category_id": category_id, "name": "Dominadas",
        "levels": _levels([_criterion("Postura", 100)]),
    })).json()["data"]
    before = (await ctx.client.get(f"/api/admin/catalog/skills/{created['id']}", headers=ctx.admin)).json()
    rejected = await ctx.client.put(f"/api/admin/catalog/skills/{created['id']}", headers=ctx.admin, json={
        "category_id": category_id, "name": "Dominadas renombrada", "min_approval_threshold": 70,
        "levels": _levels([_criterion("Postura", 33.333), _criterion("Ritmo", 33.333)]),
    })
    assert rejected.status_code == 400
    assert rejected.json()["message"] == "Los porcentajes de los criterios del nivel «Básico» deben sumar 100% (actual: 66.67%)."
    assert rejected.json()["data"] is None
    after = (await ctx.client.get(f"/api/admin/catalog/skills/{created['id']}", headers=ctx.admin)).json()
    assert after == before
    # Within the ±0.01 tolerance the write is accepted.
    accepted = await ctx.client.put(f"/api/admin/catalog/skills/{created['id']}", headers=ctx.admin, json={
        "category_id": category_id, "name": "Dominadas",
        "levels": _levels([_criterion("A", 33.333), _criterion("B", 33.333), _criterion("C", 33.334)]),
    })
    assert accepted.status_code == 200, accepted.text


@pytest.mark.asyncio
async def test_criterion_key_is_preserved_on_update_and_generated_when_missing(catalog_client):
    ctx = catalog_client
    category_id = (await ctx.client.post("/api/admin/catalog/categories", headers=ctx.admin, json={"name": "Deportes"})).json()["data"]["id"]
    created = (await ctx.client.post("/api/admin/catalog/skills", headers=ctx.admin, json={
        "category_id": category_id, "name": "Dominadas",
        "levels": _levels([_criterion("Postura", 50, key="postura-base"), _criterion("Ritmo", 50)]),
    })).json()["data"]
    first, second = created["levels"][0]["rubric"]["criteria"]
    assert first["key"] == "postura-base"
    assert second["key"]
    updated = await ctx.client.put(f"/api/admin/catalog/skills/{created['id']}", headers=ctx.admin, json={
        "category_id": category_id, "name": "Dominadas",
        "levels": _levels([
            _criterion("Ritmo renombrado", 30, key=second["key"]),
            _criterion("Postura", 70, key=first["key"]),
        ]),
    })
    assert updated.status_code == 200, updated.text
    criteria = updated.json()["data"]["levels"][0]["rubric"]["criteria"]
    assert [(c["key"], c["name"]) for c in criteria] == [(second["key"], "Ritmo renombrado"), ("postura-base", "Postura")]
    reread = (await ctx.client.get(f"/api/admin/catalog/skills/{created['id']}", headers=ctx.admin)).json()["data"]
    assert [c["key"] for c in reread["levels"][0]["rubric"]["criteria"]] == [second["key"], "postura-base"]


@pytest.mark.asyncio
async def test_ball_touch_streak_requires_positive_target(catalog_client):
    ctx = catalog_client
    category_id = (await ctx.client.post("/api/admin/catalog/categories", headers=ctx.admin, json={"name": "Deportes"})).json()["data"]["id"]
    before = await _catalog_snapshot(ctx)
    missing = await ctx.client.post("/api/admin/catalog/skills", headers=ctx.admin, json={
        "category_id": category_id, "name": "Dominadas",
        "levels": _levels([_criterion("Toques", 100, metric_type="BALL_TOUCH_STREAK")]),
    })
    assert missing.status_code == 400
    assert missing.json() == {
        "statuscode": 400,
        "message": "El criterio «Toques» del nivel «Básico» requiere un objetivo (target) mayor a 0 para el tipo BALL_TOUCH_STREAK.",
        "data": None,
    }
    for bad in ({"metric_type": "BALL_TOUCH_STREAK", "target": 0}, {"metric_type": "UNKNOWN"}):
        response = await ctx.client.post("/api/admin/catalog/skills", headers=ctx.admin, json={
            "category_id": category_id, "name": "Dominadas", "levels": _levels([_criterion("Toques", 100, **bad)]),
        })
        assert response.status_code == 422
        assert response.json()["data"] is None
    assert await _catalog_snapshot(ctx) == before
    accepted = await ctx.client.post("/api/admin/catalog/skills", headers=ctx.admin, json={
        "category_id": category_id, "name": "Dominadas",
        "levels": _levels([_criterion("Toques", 100, metric_type="BALL_TOUCH_STREAK", target=20)]),
    })
    assert accepted.status_code == 201, accepted.text
    criterion = accepted.json()["data"]["levels"][0]["rubric"]["criteria"][0]
    assert criterion["metric_type"] == "BALL_TOUCH_STREAK" and criterion["target"] == 20


@pytest.mark.asyncio
async def test_legacy_criteria_and_levels_without_criteria_still_read_without_rewrite(catalog_client, isolated_db):
    from sqlalchemy import select

    from app.models.catalog import Category, Rubric, Skill, SkillLevel

    ctx = catalog_client
    legacy_criteria = [
        {"name": "Precisión y Ejecución Técnica", "weight": 30, "description": "Legado"},
        {"name": "Fundamentos Teóricos", "weight": 30, "description": "Legado"},
    ]
    category = Category(name="Legado", slug="legado")
    skill = Skill(category=category, name="Guitarra legada", slug="guitarra-legada")
    skill.levels = [
        SkillLevel(level_number=1, name="Principiante", rubric=Rubric(min_score=70, criteria=list(legacy_criteria))),
        SkillLevel(level_number=2, name="Elemental", rubric=Rubric(min_score=70, criteria=[])),
        SkillLevel(level_number=3, name="Intermedio"),
    ]
    isolated_db.add(skill)
    await isolated_db.commit()

    first = await ctx.client.get(f"/api/admin/catalog/skills/{skill.id}", headers=ctx.admin)
    second = await ctx.client.get(f"/api/admin/catalog/skills/{skill.id}", headers=ctx.admin)
    assert first.status_code == 200, first.text
    assert first.json() == second.json()
    levels = first.json()["data"]["levels"]
    criteria = levels[0]["rubric"]["criteria"]
    assert [c["name"] for c in criteria] == [c["name"] for c in legacy_criteria]
    assert all(c["key"] and c["metric_type"] == "REFERENCE_REPLICATION" and c["target"] is None for c in criteria)
    assert len({c["key"] for c in criteria}) == 2
    assert levels[1]["rubric"]["criteria"] == []
    assert levels[2]["rubric"] is None
    skill_id = skill.id
    isolated_db.expire_all()
    stored = (await isolated_db.execute(select(Rubric.criteria).join(SkillLevel).where(SkillLevel.skill_id == skill_id, SkillLevel.level_number == 1))).scalar_one()
    assert stored == legacy_criteria


@pytest.mark.asyncio
async def test_update_without_keys_reuses_stored_keys_by_criterion_name(catalog_client):
    ctx = catalog_client
    category_id = (await ctx.client.post("/api/admin/catalog/categories", headers=ctx.admin, json={"name": "Deportes"})).json()["data"]["id"]
    created = (await ctx.client.post("/api/admin/catalog/skills", headers=ctx.admin, json={
        "category_id": category_id, "name": "Dominadas",
        "levels": _levels([_criterion("Postura", 50), _criterion("Ritmo", 50, key="ritmo")]),
    })).json()["data"]
    stored = {c["name"]: c["key"] for c in created["levels"][0]["rubric"]["criteria"]}
    # Reordered, renamed weights and no keys at all: matching names keep their stored keys.
    updated = await ctx.client.put(f"/api/admin/catalog/skills/{created['id']}", headers=ctx.admin, json={
        "category_id": category_id, "name": "Dominadas",
        "levels": _levels([_criterion("Nuevo", 20), _criterion("ritmo ", 30), _criterion("Postura", 50)]),
    })
    assert updated.status_code == 200, updated.text
    criteria = updated.json()["data"]["levels"][0]["rubric"]["criteria"]
    assert criteria[1]["key"] == "ritmo"
    assert criteria[2]["key"] == stored["Postura"]
    assert criteria[0]["key"] not in stored.values()
