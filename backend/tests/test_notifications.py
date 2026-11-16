"""HU-25 test-first contract. Real JWT/DB, request transactions rolled back.

No production routers or notification models are installed by this harness.
Missing routes/models are expected red-phase failures, never skips or xfails.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, revoke_token
from app.db.session import get_db
from app.main import create_application
from app.models.user import User

pytestmark = pytest.mark.hu25
LIST = "/api/notifications"
PREFS = "/api/users/me/notification-preferences"
DEFAULTS = {
    "revision": 0,
    "channels": {"in_app": True, "push": False, "email": False},
    "categories": {"INTERCHANGES": True, "POINTS": True, "GENERAL": True},
}
OPERATIONS = [
    (LIST, "get"), (LIST + "/{id}/read", "patch"),
    (LIST + "/read-all", "patch"), (LIST + "/{id}", "delete"),
    (PREFS, "get"), (PREFS, "put"),
]


def assert_error(response, status):
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"statuscode", "message", "data"}
    assert body["statuscode"] == status and body["data"] is None
    assert isinstance(body["message"], str) and body["message"]
    if status == 404:
        assert body["message"] == "Recurso no encontrado"


def success(response, message, listed=False):
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == ({"statuscode", "message", "data", "count"} if listed else {"statuscode", "message", "data"})
    assert body["statuscode"] == 200 and body["message"] == message
    return body


@pytest.mark.parametrize(("path", "method"), OPERATIONS)
def test_required_openapi_contract(path, method):
    paths = create_application().openapi()["paths"]
    assert path in paths, f"HU-25 route missing: {method.upper()} {path}"
    operation = paths[path][method]
    assert {"200", "401", "403", "423"} <= operation["responses"].keys()
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]
    if "{id}" in path:
        identifier = next(p for p in operation["parameters"] if p["name"] == "id")
        assert identifier["schema"]["format"] == "uuid"
        assert "404" in operation["responses"]
    if method == "put":
        assert {"409", "422"} <= operation["responses"].keys()
        assert operation["requestBody"]["required"]


@pytest.fixture
async def inbox():
    engine = create_async_engine(settings.async_database_url, pool_pre_ping=True)
    app = create_application()
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                async with AsyncSession(bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint") as db:
                    suffix = uuid4().hex
                    users = [User(id=uuid4(), email=f"hu25-{suffix}-{i}@example.invalid", full_name=f"HU25 {i}", role=role, is_active=True, is_locked=False)
                             for i, role in enumerate(["MEMBER", "MEMBER", "ADMIN"])]
                    db.add_all(users)
                    await db.commit()

                    async def request_db():
                        async with AsyncSession(bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint") as session:
                            try:
                                yield session
                                await session.commit()
                            except Exception:
                                await session.rollback()
                                raise

                    app.dependency_overrides[get_db] = request_db
                    tokens = [create_access_token(str(u.id), u.role, timedelta(minutes=5)) for u in users]
                    headers = [{"Authorization": "Bearer " + token} for token in tokens]
                    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://testserver") as client:
                        yield SimpleNamespace(client=client, db=db, users=users, headers=headers, tokens=tokens)
            finally:
                app.dependency_overrides.clear()
                await transaction.rollback()
    finally:
        await engine.dispose()


async def seed(inbox, owner=0, **values):
    # Import at use time: missing HU-25 modules must not prevent regression collection.
    from app.models.notification import Notification
    item = Notification(id=uuid4(), user_id=inbox.users[owner].id, event_id=uuid4(),
                        type=values.pop("type", "MATCH_RECEIVED"), title="Nuevo aviso", message="Mensaje de prueba", **values)
    inbox.db.add(item)
    await inbox.db.commit()
    return item


async def emit(inbox, owner=0, **changes):
    from app.services.notification_service import NotificationService
    return await NotificationService.emit_in_app(inbox.db, user_id=inbox.users[owner].id,
        event_id=changes.pop("event_id", uuid4()), notification_type=changes.pop("notification_type", "MATCH_RECEIVED"),
        title=changes.pop("title", "Nuevo aviso"), message=changes.pop("message", "Mensaje de prueba"), **changes)


@pytest.mark.parametrize("owner", [0, 2])
async def test_empty_inbox_and_default_preferences_for_both_roles(inbox, owner):
    response = await inbox.client.get(LIST, headers=inbox.headers[owner])
    body = success(response, "Notificaciones recuperadas exitosamente.", listed=True)
    assert body["data"] == [] and body["count"] == 0
    preferences = await inbox.client.get(PREFS, headers=inbox.headers[owner])
    assert success(preferences, "Preferencias de notificaciones recuperadas exitosamente.")["data"] == DEFAULTS
    assert await inbox.db.scalar(text("SELECT count(*) FROM notification_preferences WHERE user_id = :id"), {"id": inbox.users[owner].id}) == 0


@pytest.mark.parametrize(("path", "method"), OPERATIONS)
@pytest.mark.parametrize("kind", ["absent", "malformed", "expired", "refresh", "revoked"])
async def test_authentication_is_required(inbox, path, method, kind):
    # Ensure an absent route returning 404 is never counted as a passing auth test.
    assert path in create_application().openapi()["paths"], "HU-25 route not implemented"
    tokens = {"malformed": "invalid", "expired": create_access_token(str(inbox.users[0].id), "MEMBER", timedelta(seconds=-1)),
              "refresh": create_refresh_token(str(inbox.users[0].id), "MEMBER"), "revoked": inbox.tokens[0]}
    if kind == "revoked":
        revoke_token(inbox.tokens[0])
    headers = {} if kind == "absent" else {"Authorization": "Bearer " + tokens[kind]}
    kwargs = {"json": deepcopy(DEFAULTS)} if method == "put" else {}
    response = await inbox.client.request(method, path.replace("{id}", str(uuid4())), headers=headers, **kwargs)
    assert_error(response, 401)


@pytest.mark.parametrize(("field", "code"), [("is_active", 403), ("is_locked", 423)])
@pytest.mark.parametrize(("path", "method"), OPERATIONS)
async def test_inactive_or_locked_account(inbox, field, code, path, method):
    setattr(inbox.users[0], field, field == "is_locked")
    await inbox.db.commit()
    kwargs = {"json": deepcopy(DEFAULTS)} if method == "put" else {}
    response = await inbox.client.request(method, path.replace("{id}", str(uuid4())), headers=inbox.headers[0], **kwargs)
    assert_error(response, code)


@pytest.mark.parametrize("owner", [0, 2])
async def test_read_is_idempotent_and_delete_is_private_soft_delete(inbox, owner):
    item = await seed(inbox, owner)
    path = f"{LIST}/{item.id}"
    first = await inbox.client.patch(path + "/read", headers=inbox.headers[owner])
    data = success(first, "Notificación marcada como leída.")["data"]
    assert data["read_at"] is not None
    again = await inbox.client.patch(path + "/read", headers=inbox.headers[owner])
    assert success(again, "Notificación marcada como leída.")["data"]["read_at"] == data["read_at"]
    deleted = await inbox.client.delete(path, headers=inbox.headers[owner])
    assert success(deleted, "Notificación eliminada exitosamente.")["data"] is None
    assert await inbox.db.scalar(text("SELECT deleted_at FROM notifications WHERE id = :id"), {"id": item.id}) is not None
    assert_error(await inbox.client.delete(path, headers=inbox.headers[owner]), 404)
    assert_error(await inbox.client.patch(path + "/read", headers=inbox.headers[owner]), 404)


@pytest.mark.parametrize("actor", [1, 2])
async def test_other_member_or_admin_cannot_read_or_delete_another_users_notice(inbox, actor):
    item = await seed(inbox)
    assert_error(await inbox.client.patch(f"{LIST}/{item.id}/read", headers=inbox.headers[actor]), 404)
    assert_error(await inbox.client.delete(f"{LIST}/{item.id}", headers=inbox.headers[actor]), 404)
    response = await inbox.client.get(LIST, headers=inbox.headers[actor])
    assert success(response, "Notificaciones recuperadas exitosamente.", True)["count"] == 0


async def test_filter_pagination_global_unread_and_private_dto(inbox):
    now = datetime.now(timezone.utc)
    a = await seed(inbox, created_at=now - timedelta(minutes=3))
    b = await seed(inbox, type="POINTS_RECEIVED", created_at=now - timedelta(minutes=2))
    await seed(inbox, type="OTHER", read_at=now, created_at=now - timedelta(minutes=1))
    await seed(inbox, deleted_at=now)
    await seed(inbox, owner=1)
    page = await inbox.client.get(LIST, headers=inbox.headers[0], params={"page_size": 1, "page": 2})
    body = success(page, "Notificaciones recuperadas exitosamente.", True)
    assert body["count"] == 3 and body["data"][0]["id"] == str(b.id)
    assert set(body["data"][0]) == {"id", "type", "category", "title", "message", "created_at", "read_at"}
    for params, total in [({"unread": True, "page_size": 1}, 2), ({"unread": False}, 1),
                          ({"category": "INTERCHANGES"}, 1), ({"category": "POINTS", "unread": True}, 1)]:
        filtered = await inbox.client.get(LIST, headers=inbox.headers[0], params=params)
        assert success(filtered, "Notificaciones recuperadas exitosamente.", True)["count"] == total
    empty = await inbox.client.get(LIST, headers=inbox.headers[0], params={"page": 999})
    assert empty.json()["data"] == [] and empty.json()["count"] == 3
    assert a.id != b.id


async def test_creation_time_ties_use_uuid_order(inbox):
    now = datetime.now(timezone.utc)
    items = [await seed(inbox, created_at=now) for _ in range(3)]
    response = await inbox.client.get(LIST, headers=inbox.headers[0])
    assert response.status_code == 200
    assert [row["id"] for row in response.json()["data"]] == sorted(str(item.id) for item in items)


async def test_read_all_only_affects_existing_own_notifications(inbox):
    first = await seed(inbox)
    foreign = await seed(inbox, owner=1)
    deleted = await seed(inbox, deleted_at=datetime.now(timezone.utc))
    response = await inbox.client.patch(LIST + "/read-all", headers=inbox.headers[0])
    assert success(response, "Notificaciones marcadas como leídas.")["data"] is None
    assert await inbox.db.scalar(text("SELECT read_at FROM notifications WHERE id = :id"), {"id": first.id}) is not None
    for item in [foreign, deleted]:
        assert await inbox.db.scalar(text("SELECT read_at FROM notifications WHERE id = :id"), {"id": item.id}) is None
    await seed(inbox)
    response = await inbox.client.get(LIST, headers=inbox.headers[0], params={"unread": True})
    assert response.json()["count"] == 1
    success(await inbox.client.patch(LIST + "/read-all", headers=inbox.headers[0]), "Notificaciones marcadas como leídas.")
    success(await inbox.client.patch(LIST + "/read-all", headers=inbox.headers[0]), "Notificaciones marcadas como leídas.")


@pytest.mark.parametrize("params", [{"page": 0}, {"page_size": 0}, {"page_size": 101}, {"category": "INVALID"}, {"unread": "invalid"}])
async def test_invalid_filters(inbox, params):
    assert_error(await inbox.client.get(LIST, headers=inbox.headers[0], params=params), 422)


@pytest.mark.parametrize("owner", [0, 2])
async def test_preferences_persist_reopen_and_reject_stale_revision(inbox, owner):
    payload = deepcopy(DEFAULTS)
    payload["channels"]["push"] = True
    response = await inbox.client.put(PREFS, headers=inbox.headers[owner], json=payload)
    saved = success(response, "Preferencias de notificaciones actualizadas exitosamente.")["data"]
    assert saved == {**payload, "revision": 1}
    reopened = await inbox.client.get(PREFS, headers=inbox.headers[owner])
    assert reopened.json()["data"] == saved
    conflict = await inbox.client.put(PREFS, headers=inbox.headers[owner], json=payload)
    assert_error(conflict, 409)
    assert conflict.json()["message"] == "Las preferencias cambiaron. Recarga la configuración antes de guardar."
    saved["channels"]["email"] = True
    updated = await inbox.client.put(PREFS, headers=inbox.headers[owner], json=saved)
    assert updated.json()["data"]["revision"] == 2
    other = await inbox.client.get(PREFS, headers=inbox.headers[1])
    assert other.json()["data"] == DEFAULTS


@pytest.mark.parametrize("mutation", ["missing_channel", "missing_categories", "unknown_channel", "unknown_category", "string_boolean", "boolean_revision", "negative_revision", "extra_user", "missing_revision"])
async def test_preferences_require_full_strict_body(inbox, mutation):
    body = deepcopy(DEFAULTS)
    if mutation == "missing_channel":
        del body["channels"]["email"]
    elif mutation == "missing_categories":
        del body["categories"]
    elif mutation == "unknown_channel":
        body["channels"]["sms"] = True
    elif mutation == "unknown_category":
        body["categories"]["SECRET"] = True
    elif mutation == "string_boolean":
        body["channels"]["push"] = "false"
    elif mutation == "boolean_revision":
        body["revision"] = True
    elif mutation == "negative_revision":
        body["revision"] = -1
    elif mutation == "missing_revision":
        del body["revision"]
    else:
        body["user_id"] = str(inbox.users[1].id)
    assert_error(await inbox.client.put(PREFS, headers=inbox.headers[0], json=body), 422)


async def test_internal_emission_respects_preferences_and_preserves_history(inbox):
    original = await emit(inbox)
    assert original is not None
    payload = deepcopy(DEFAULTS)
    payload["channels"]["in_app"] = False
    response = await inbox.client.put(PREFS, headers=inbox.headers[0], json=payload)
    assert response.status_code == 200
    assert await emit(inbox) is None
    listed = await inbox.client.get(LIST, headers=inbox.headers[0])
    assert listed.json()["count"] == 1 and listed.json()["data"][0]["id"] == str(original.id)
    payload = response.json()["data"]
    payload["channels"]["in_app"] = True
    payload["categories"]["INTERCHANGES"] = False
    assert (await inbox.client.put(PREFS, headers=inbox.headers[0], json=payload)).status_code == 200
    assert await emit(inbox) is None
    assert await emit(inbox, notification_type="POINTS_RECEIVED") is not None


async def test_event_deduplication_is_per_recipient_and_never_resurrects_deleted_notice(inbox):
    event = uuid4()
    first = await emit(inbox, event_id=event)
    duplicate = await emit(inbox, event_id=event)
    assert duplicate.id == first.id
    other = await emit(inbox, owner=1, event_id=event)
    assert other.id != first.id
    await inbox.db.commit()
    assert (await inbox.client.delete(f"{LIST}/{first.id}", headers=inbox.headers[0])).status_code == 200
    await emit(inbox, event_id=event)
    response = await inbox.client.get(LIST, headers=inbox.headers[0])
    assert response.json()["count"] == 0


@pytest.mark.parametrize("changes", [{"title": " "}, {"title": "x" * 151}, {"message": " "}, {"message": "x" * 2001}, {"notification_type": "INVALID"}])
async def test_internal_emission_rejects_invalid_content(inbox, changes):
    from pydantic import ValidationError
    from app.core.exceptions import SkillMatchException
    with pytest.raises((ValueError, ValidationError, SkillMatchException)):
        await emit(inbox, **changes)


async def test_internal_emission_accepts_exact_limits_and_normalizes_text(inbox):
    item = await emit(inbox, title=" " + "t" * 150 + " ", message=" " + "m" * 2000 + " ")
    assert item.title == "t" * 150 and item.message == "m" * 2000


@pytest.mark.parametrize("method", ["patch", "delete"])
@pytest.mark.parametrize(("identifier", "status"), [("invalid", 422), (str(uuid4()), 404)])
async def test_invalid_and_missing_notification(inbox, method, identifier, status):
    path = f"{LIST}/{identifier}" + ("/read" if method == "patch" else "")
    assert_error(await inbox.client.request(method, path, headers=inbox.headers[0]), status)


async def test_internal_event_conflict_never_overwrites_original(inbox):
    from app.core.exceptions import SkillMatchException
    event = uuid4()
    original = await emit(inbox, event_id=event)
    with pytest.raises(SkillMatchException):
        await emit(inbox, event_id=event, message="Different event content")
    await inbox.db.refresh(original)
    assert original.message == "Mensaje de prueba"
