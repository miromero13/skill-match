"""HU-16 acceptance contract over the implemented API and real PostgreSQL.

Run explicitly with ``pytest -m hu16`` against configured local PostgreSQL.
No schema is created or migrated. Every fixture transaction is rolled back.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.core.security import create_access_token
from app.db.session import get_db
from app.main import create_application
from app.models.catalog import Category, Skill
from app.models.teaching_skill import TeachingSkill
from app.models.user import User, UserRole

pytestmark = pytest.mark.hu16
BASE = "/api/users/me/teaching-skills"
VALID = {
    "title": "Proyecto Python",
    "description": "Repositorio de demostración",
    "url": "https://github.com/example/project",
    "evidence_type": "REPOSITORY",
}


def assert_error(response, code):
    assert response.status_code == code
    body = response.json()
    assert set(body) == {"statuscode", "message", "data"}
    assert body["statuscode"] == code
    assert body["data"] is None
    assert isinstance(body["message"], str) and body["message"]


@pytest.fixture
async def evidence_api():
    engine = create_async_engine(settings.async_database_url, pool_pre_ping=True)
    app = create_application()
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                async with AsyncSession(
                    bind=connection, expire_on_commit=False,
                    join_transaction_mode="create_savepoint",
                ) as db:
                    suffix = uuid4().hex
                    users = [
                        User(
                            id=uuid4(), email=f"hu16-{label}-{suffix}@example.invalid",
                            full_name=f"HU16 {label}", role=role,
                            is_active=True, is_locked=False, hashed_password=None,
                        )
                        for label, role in [
                            ("A", UserRole.MEMBER), ("B", UserRole.MEMBER),
                            ("admin", UserRole.ADMIN),
                        ]
                    ]
                    category = Category(
                        id=uuid4(), name="HU16 temporary", slug=f"hu16-{suffix}", is_active=True,
                    )
                    db.add_all([*users, category])
                    await db.flush()
                    skills = [
                        Skill(
                            id=uuid4(), category_id=category.id, name=f"HU16 {i}",
                            slug=f"hu16-{suffix}-{i}", is_active=True,
                        ) for i in range(2)
                    ]
                    db.add_all(skills)
                    await db.flush()
                    offers = [
                        TeachingSkill(
                            id=uuid4(), user_id=owner.id, skill_id=skill.id,
                            declared_level="BEGINNER", years_of_experience=1,
                            accepts_points=False, hourly_points_rate=None,
                            status="DECLARADA",
                        )
                        for owner, skill in [
                            (users[0], skills[0]), (users[0], skills[1]), (users[2], skills[0]),
                        ]
                    ]
                    db.add_all(offers)
                    await db.flush()

                    async def transaction_db():
                        # Una sesión por solicitud, igual que get_db en producción.
                        # El rollback de un error no expira objetos del harness.
                        async with AsyncSession(
                            bind=connection, expire_on_commit=False,
                            join_transaction_mode="create_savepoint",
                        ) as request_db:
                            try:
                                yield request_db
                                await request_db.commit()
                            except Exception:
                                await request_db.rollback()
                                raise

                    # Commit fixtures only to the savepoint, never the outer transaction.
                    await db.commit()
                    app.dependency_overrides[get_db] = transaction_db
                    headers = [
                        {"Authorization": "Bearer " + create_access_token(
                            str(user.id), user.role.value, timedelta(minutes=5),
                        )} for user in users
                    ]
                    transport = ASGITransport(app=app, raise_app_exceptions=False)
                    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                        yield client, db, headers, offers, users
            finally:
                app.dependency_overrides.clear()
                await transaction.rollback()
    finally:
        await engine.dispose()


async def create_evidence(api, offer_index=0, owner_index=0, **changes):
    client, _, headers, offers, _ = api
    response = await client.post(
        f"{BASE}/{offers[offer_index].id}/evidences",
        headers=headers[owner_index], json={**VALID, **changes},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body) == {"statuscode", "message", "data"}
    assert body["statuscode"] == 201
    assert body["message"] == "Evidencia registrada exitosamente."
    return body["data"]


@pytest.mark.parametrize(("owner", "offer"), [(0, 0), (2, 2)])
async def test_owner_crud_and_persistence(evidence_api, owner, offer):
    client, _, headers, offers, _ = evidence_api
    path = f"{BASE}/{offers[offer].id}/evidences"
    empty = await client.get(path, headers=headers[owner])
    assert empty.status_code == 200
    assert empty.json()["data"] == [] and empty.json()["count"] == 0
    item = await create_evidence(evidence_api, offer, owner)
    assert item["teaching_skill_id"] == str(offers[offer].id)
    assert item["created_at"] and item["updated_at"]
    listed = await client.get(path, headers=headers[owner])
    assert listed.json()["count"] == 1
    assert listed.json()["message"] == "Evidencias recuperadas exitosamente."
    assert listed.json()["data"][0]["id"] == item["id"]
    updated = await client.put(
        f"{path}/{item['id']}", headers=headers[owner],
        json={"title": "  Nuevo título  ", "url": VALID["url"], "evidence_type": "VIDEO"},
    )
    assert updated.status_code == 200
    assert updated.json()["message"] == "Evidencia actualizada exitosamente."
    assert updated.json()["data"]["title"] == "Nuevo título"
    assert updated.json()["data"]["description"] is None
    assert "count" not in updated.json()
    deleted = await client.delete(f"{path}/{item['id']}", headers=headers[owner])
    assert deleted.status_code == 200
    assert deleted.json()["message"] == "Evidencia eliminada exitosamente."
    assert deleted.json()["data"] is None and "count" not in deleted.json()
    assert (await client.get(path, headers=headers[owner])).json()["count"] == 0
    assert_error(await client.delete(f"{path}/{item['id']}", headers=headers[owner]), 404)


@pytest.mark.parametrize("actor", [None, 1, 2])
@pytest.mark.parametrize("method", ["GET", "POST", "PUT", "DELETE"])
async def test_anonymous_and_other_users_cannot_access(evidence_api, actor, method):
    client, _, headers, offers, _ = evidence_api
    path = f"{BASE}/{offers[0].id}/evidences"
    if method in {"PUT", "DELETE"}:
        item = await create_evidence(evidence_api)
        path += f"/{item['id']}"
    response = await client.request(
        method, path, headers={} if actor is None else headers[actor],
        **({"json": VALID} if method in {"POST", "PUT"} else {}),
    )
    assert_error(response, 401 if actor is None else 404)


@pytest.mark.parametrize("method", ["PUT", "DELETE"])
async def test_evidence_cannot_be_addressed_through_another_own_skill(evidence_api, method):
    client, _, headers, offers, _ = evidence_api
    item = await create_evidence(evidence_api)
    response = await client.request(
        method, f"{BASE}/{offers[1].id}/evidences/{item['id']}", headers=headers[0],
        **({"json": VALID} if method == "PUT" else {}),
    )
    assert_error(response, 404)


@pytest.mark.parametrize("method", ["POST", "PUT"])
@pytest.mark.parametrize(
    "changes",
    [
        {"title": "   "}, {"title": "x" * 151}, {"description": "x" * 2001},
        {"url": "not-a-url"}, {"url": "javascript:alert(1)"},
        {"url": "file:///tmp/demo"}, {"url": "ftp://example.com/demo"},
        {"url": "https://user:password@example.com/demo"},
        {"url": "https://example.com/" + "x" * 2048},
        {"evidence_type": "UNKNOWN"}, {"user_id": str(uuid4())},
        {"teaching_skill_id": str(uuid4())}, {"id": str(uuid4())},
        {"created_at": "2026-01-01T00:00:00Z"},
    ],
)
async def test_invalid_writes_use_error_contract(evidence_api, method, changes):
    client, _, headers, offers, _ = evidence_api
    path = f"{BASE}/{offers[0].id}/evidences"
    if method == "PUT":
        item = await create_evidence(evidence_api)
        path += f"/{item['id']}"
    assert_error(await client.request(method, path, headers=headers[0], json={**VALID, **changes}), 422)


@pytest.mark.parametrize("kind", ["REPOSITORY", "VIDEO", "CERTIFICATE", "OTHER"])
@pytest.mark.parametrize("scheme", ["http", "https"])
async def test_allowed_types_and_url_schemes(evidence_api, kind, scheme):
    item = await create_evidence(
        evidence_api, title="  Evidencia  ", description="  ", evidence_type=kind,
        url=f"{scheme}://example.com/evidence?version=1#demo",
    )
    assert item["title"] == "Evidencia" and item["description"] is None
    assert item["url"] == f"{scheme}://example.com/evidence?version=1#demo"
    assert item["evidence_type"] == kind


async def test_duplicates_are_scoped_to_skill_and_normalized(evidence_api):
    client, _, headers, offers, _ = evidence_api
    await create_evidence(evidence_api, url="https://EXAMPLE.COM")
    path = f"{BASE}/{offers[0].id}/evidences"
    duplicate = await client.post(path, headers=headers[0], json={**VALID, "url": "https://example.com/"})
    assert_error(duplicate, 409)
    assert duplicate.json()["message"] == "Ya registraste esta evidencia."
    await create_evidence(evidence_api, offer_index=1, url="https://example.com/")
    assert (await client.get(path, headers=headers[0])).json()["count"] == 1


async def test_update_rejects_duplicate_but_accepts_unchanged_url(evidence_api):
    client, _, headers, offers, _ = evidence_api
    first = await create_evidence(evidence_api)
    second = await create_evidence(evidence_api, url="https://example.com/second")
    path = f"{BASE}/{offers[0].id}/evidences"
    duplicate = await client.put(f"{path}/{second['id']}", headers=headers[0], json=VALID)
    assert_error(duplicate, 409)
    unchanged = await client.put(f"{path}/{first['id']}", headers=headers[0], json=VALID)
    assert unchanged.status_code == 200


@pytest.mark.parametrize("missing", ["title", "url", "evidence_type"])
async def test_put_requires_complete_editable_fields(evidence_api, missing):
    client, _, headers, offers, _ = evidence_api
    item = await create_evidence(evidence_api)
    payload = {key: value for key, value in VALID.items() if key != missing}
    response = await client.put(
        f"{BASE}/{offers[0].id}/evidences/{item['id']}", headers=headers[0], json=payload,
    )
    assert_error(response, 422)


@pytest.mark.parametrize("method", ["PUT", "DELETE"])
@pytest.mark.parametrize(("identifier", "code"), [("invalid", 422), (str(uuid4()), 404)])
async def test_invalid_or_missing_evidence(evidence_api, method, identifier, code):
    client, _, headers, offers, _ = evidence_api
    response = await client.request(
        method, f"{BASE}/{offers[0].id}/evidences/{identifier}", headers=headers[0],
        **({"json": VALID} if method == "PUT" else {}),
    )
    assert_error(response, code)


@pytest.mark.parametrize(("field", "code"), [("is_active", 403), ("is_locked", 423)])
async def test_inactive_or_locked_owner_is_rejected(evidence_api, field, code):
    client, db, headers, offers, users = evidence_api
    setattr(users[0], field, field == "is_locked")
    await db.commit()
    response = await client.get(f"{BASE}/{offers[0].id}/evidences", headers=headers[0])
    assert_error(response, code)


async def test_pagination_total_and_order(evidence_api):
    client, _, headers, offers, _ = evidence_api
    items = [await create_evidence(evidence_api, url=f"https://example.com/{i}") for i in range(3)]
    path = f"{BASE}/{offers[0].id}/evidences"
    first = await client.get(path, headers=headers[0], params={"page_size": 2})
    second = await client.get(path, headers=headers[0], params={"page_size": 2, "page": 2})
    assert first.json()["count"] == second.json()["count"] == 3
    ordered = first.json()["data"] + second.json()["data"]
    assert [item["id"] for item in ordered] == [item["id"] for item in reversed(items)]
    empty = await client.get(path, headers=headers[0], params={"page": 99})
    assert empty.json()["data"] == [] and empty.json()["count"] == 3


async def test_equal_creation_times_are_sorted_by_uuid(evidence_api):
    client, db, headers, offers, _ = evidence_api
    items = [await create_evidence(evidence_api, url=f"https://example.com/{i}") for i in range(3)]
    await db.execute(
        text("UPDATE skill_evidences SET created_at = :created WHERE teaching_skill_id = :id"),
        {"created": datetime(2026, 1, 1, tzinfo=timezone.utc), "id": offers[0].id},
    )
    await db.commit()
    response = await client.get(f"{BASE}/{offers[0].id}/evidences", headers=headers[0])
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["data"]] == sorted(item["id"] for item in items)


async def test_exact_limits_are_accepted_by_api(evidence_api):
    prefix = "https://example.com/"
    item = await create_evidence(
        evidence_api, title="x" * 150, description="x" * 2000,
        url=prefix + "x" * (2048 - len(prefix)),
    )
    assert len(item["title"]) == 150
    assert len(item["description"]) == 2000
    assert len(item["url"]) == 2048


@pytest.mark.parametrize("params", [{"page": 0}, {"page_size": 0}, {"page_size": 101}])
async def test_invalid_pagination(evidence_api, params):
    client, _, headers, offers, _ = evidence_api
    assert_error(await client.get(f"{BASE}/{offers[0].id}/evidences", headers=headers[0], params=params), 422)


@pytest.mark.parametrize("method", ["GET", "POST", "PUT", "DELETE"])
@pytest.mark.parametrize(("identifier", "code"), [("invalid", 422), (str(uuid4()), 404)])
async def test_invalid_or_missing_parent(evidence_api, method, identifier, code):
    client, _, headers, _, _ = evidence_api
    path = f"{BASE}/{identifier}/evidences"
    if method in {"PUT", "DELETE"}:
        path += f"/{uuid4()}"
    assert_error(await client.request(
        method, path, headers=headers[0],
        **({"json": VALID} if method in {"POST", "PUT"} else {}),
    ), code)


async def test_deleting_parent_cascades_in_postgresql(evidence_api):
    client, db, headers, offers, _ = evidence_api
    item = await create_evidence(evidence_api)
    deleted = await client.delete(f"{BASE}/{offers[0].id}", headers=headers[0])
    assert deleted.status_code == 200
    remaining = await db.scalar(
        text("SELECT count(*) FROM skill_evidences WHERE id = :id"), {"id": item["id"]},
    )
    assert remaining == 0


async def test_exact_openapi_routes_and_response_models():
    app = create_application()
    paths = app.openapi()["paths"]
    collection = f"{BASE}/{{id}}/evidences"
    detail = collection + "/{evidence_id}"
    for path, method, code in [
        (collection, "get", "200"), (collection, "post", "201"),
        (detail, "put", "200"), (detail, "delete", "200"),
    ]:
        assert path in paths, f"HU-16 route missing: {path}"
        operation = paths[path][method]
        assert operation["responses"][code]["content"]["application/json"]["schema"]
        assert {"401", "403", "404", "422", "423"} <= operation["responses"].keys()
        if method in {"post", "put"}:
            assert "409" in operation["responses"]
        for parameter in operation["parameters"]:
            if parameter["in"] == "path":
                assert parameter["schema"]["format"] == "uuid"
