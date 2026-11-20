"""Native push (FCM) credentials, async send, post-commit dispatch and admin diagnostics (native-push S2-S7).

firebase_admin is always mocked: no credential file is read and no request reaches Google.
"""

import asyncio
import json
from contextlib import asynccontextmanager
from unittest.mock import MagicMock
from uuid import uuid4

import httpx
import pytest
from firebase_admin import exceptions as firebase_exceptions
from firebase_admin import messaging
from pydantic import SecretStr
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.security import create_access_token
from app.db import session as db_session
from app.main import create_application
from app.models.device_push_token import DevicePushToken
from app.models.notification import Notification
from app.models.notification_preference import NotificationPreference
from app.models.user import User, UserRole
from app.services import fcm_service, notification_push_dispatcher
from app.services.fcm_service import FCMService
from app.services.notification_service import NotificationService

FAKE_KEY = "-----BEGIN PRIVATE KEY-----FAKEKEYMATERIAL-----END PRIVATE KEY-----"
FAKE_JSON = json.dumps({"type": "service_account", "project_id": "demo-test", "private_key": FAKE_KEY})


@pytest.fixture(autouse=True)
async def loop_local_sessions(monkeypatch):
    """Per-test NullPool engine for the request path: pytest-asyncio uses one loop per test and
    pooled asyncpg connections cannot cross loops. `get_db` resolves `AsyncSessionLocal` at call
    time; the dispatcher and dead-token cleanup already use the NullPool BackgroundSessionLocal."""
    engine = create_async_engine(settings.async_database_url, poolclass=NullPool)
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(db_session, "AsyncSessionLocal", factory)
    yield
    await notification_push_dispatcher.drain()
    await engine.dispose()


def _session() -> AsyncSession:
    return db_session.AsyncSessionLocal()


@pytest.fixture
def fake_firebase(monkeypatch):
    """Fresh init state and a fully mocked firebase_admin surface."""
    monkeypatch.setattr(fcm_service, "_firebase_state", fcm_service.FirebaseState())
    get_app = MagicMock(side_effect=ValueError("no app"))
    initialize_app = MagicMock()
    certificate = MagicMock(return_value=object())
    send = MagicMock(return_value="projects/demo-test/messages/1")
    monkeypatch.setattr(fcm_service.firebase_admin, "get_app", get_app)
    monkeypatch.setattr(fcm_service.firebase_admin, "initialize_app", initialize_app)
    monkeypatch.setattr(fcm_service.credentials, "Certificate", certificate)
    monkeypatch.setattr(fcm_service.messaging, "send", send)
    monkeypatch.setattr(settings, "FIREBASE_CREDENTIALS_JSON", SecretStr(FAKE_JSON))
    monkeypatch.setattr(settings, "FIREBASE_CREDENTIALS_PATH", None)
    mocks = MagicMock()
    mocks.get_app, mocks.initialize_app, mocks.certificate, mocks.send = get_app, initialize_app, certificate, send
    return mocks


@asynccontextmanager
async def _members(count: int = 1, *, push: bool | None = None, tokens: int = 0, role: UserRole = UserRole.MEMBER):
    """Committed users (optionally with push preference and active tokens); removes only what it creates."""
    suffix = uuid4().hex
    async with _session() as db:
        users = [User(email=f"push-{i}-{suffix}@example.invalid", full_name="Push Test", role=role) for i in range(count)]
        db.add_all(users)
        await db.flush()
        if push is not None:
            db.add_all([NotificationPreference(user_id=u.id, push=push) for u in users])
        token_values = {u.id: [f"fcm-{uuid4().hex}-{j}" for j in range(tokens)] for u in users}
        db.add_all([
            DevicePushToken(user_id=uid, fcm_token=value, platform="android", is_active=True)
            for uid, values in token_values.items() for value in values
        ])
        await db.commit()
    ids = [u.id for u in users]
    try:
        yield users, token_values
    finally:
        await notification_push_dispatcher.drain()
        async with _session() as db:
            await db.execute(delete(Notification).where(Notification.user_id.in_(ids)))
            await db.execute(delete(NotificationPreference).where(NotificationPreference.user_id.in_(ids)))
            await db.execute(delete(DevicePushToken).where(DevicePushToken.user_id.in_(ids)))
            await db.execute(delete(User).where(User.id.in_(ids)))
            await db.commit()


def _sent_tokens(send: MagicMock) -> list[str]:
    return [call.args[0].token for call in send.call_args_list]


# ---------------------------------------------------------------- S2 credentials

def test_init_prefers_json_env_and_records_source(fake_firebase):
    assert fcm_service._init_firebase() is True
    fake_firebase.certificate.assert_called_once_with(json.loads(FAKE_JSON))
    fake_firebase.initialize_app.assert_called_once()
    assert fcm_service.get_firebase_status() == {"initialized": True, "source": "json", "error": None}


def test_init_failure_records_safe_error_and_retries_next_time(fake_firebase):
    fake_firebase.certificate.side_effect = ValueError(f"Invalid certificate {FAKE_KEY}")
    assert fcm_service._init_firebase() is False
    status = fcm_service.get_firebase_status()
    assert status["initialized"] is False and status["source"] is None and status["error"]
    assert "PRIVATE KEY" not in status["error"] and "FAKEKEYMATERIAL" not in status["error"]
    # Next attempt retries; the error stays visible until a success replaces it.
    fake_firebase.certificate.side_effect = None
    assert fcm_service._init_firebase() is True
    assert fcm_service.get_firebase_status() == {"initialized": True, "source": "json", "error": None}
    assert fake_firebase.certificate.call_count == 2


def test_init_invalid_json_never_crashes_or_leaks(fake_firebase, monkeypatch):
    monkeypatch.setattr(settings, "FIREBASE_CREDENTIALS_JSON", SecretStr("{not json " + FAKE_KEY))
    assert fcm_service._init_firebase() is False
    status = fcm_service.get_firebase_status()
    assert status["initialized"] is False and status["error"] and "FAKEKEYMATERIAL" not in status["error"]
    fake_firebase.initialize_app.assert_not_called()


def test_init_falls_back_to_relative_path_from_cwd(fake_firebase, monkeypatch, tmp_path):
    (tmp_path / "creds.json").write_text("{}", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(settings, "FIREBASE_CREDENTIALS_JSON", None)
    monkeypatch.setattr(settings, "FIREBASE_CREDENTIALS_PATH", "creds.json")
    assert fcm_service._init_firebase() is True
    fake_firebase.certificate.assert_called_once_with(str(tmp_path / "creds.json"))
    assert fcm_service.get_firebase_status() == {"initialized": True, "source": "path", "error": None}


def test_init_absolute_path_directory_or_missing_is_a_visible_error(fake_firebase, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "FIREBASE_CREDENTIALS_JSON", None)
    monkeypatch.setattr(settings, "FIREBASE_CREDENTIALS_PATH", str(tmp_path))  # bind mount registered as a directory
    assert fcm_service._init_firebase() is False
    assert fcm_service.get_firebase_status()["error"]
    monkeypatch.setattr(settings, "FIREBASE_CREDENTIALS_PATH", str(tmp_path / "missing.json"))
    assert fcm_service._init_firebase() is False
    assert fcm_service.get_firebase_status()["initialized"] is False
    fake_firebase.certificate.assert_not_called()


def test_init_without_any_configuration_is_reported(fake_firebase, monkeypatch):
    monkeypatch.setattr(settings, "FIREBASE_CREDENTIALS_JSON", None)
    monkeypatch.setattr(settings, "FIREBASE_CREDENTIALS_PATH", None)
    assert fcm_service._init_firebase() is False
    assert fcm_service.get_firebase_status()["error"]


# ---------------------------------------------------------------- S3 sending

async def test_send_uses_to_thread_deactivates_dead_token_and_never_commits_caller(fake_firebase, monkeypatch):
    calls: list[object] = []
    real_to_thread = asyncio.to_thread

    async def spy_to_thread(func, *args, **kwargs):
        calls.append(func)
        return await real_to_thread(func, *args, **kwargs)

    monkeypatch.setattr(fcm_service.asyncio, "to_thread", spy_to_thread)
    async with _members(tokens=2) as (users, token_values):
        member = users[0]
        dead, alive = token_values[member.id]

        def send(message):
            if message.token == dead:
                raise messaging.UnregisteredError("Requested entity was not found.")
            return "projects/demo-test/messages/2"

        fake_firebase.send.side_effect = send
        async with _session() as caller:
            await caller.execute(update(User).where(User.id == member.id).values(full_name="Uncommitted"))
            results = await FCMService.send_push_to_user(
                caller, user_id=member.id, title="Hola", body="Cuerpo", data={"type": "OTHER", "n": "1"},
            )
            await caller.rollback()

        assert calls and all(func is fake_firebase.send for func in calls)
        assert sorted(results, key=lambda r: r["ok"]) == [
            {"token_suffix": dead[-8:], "ok": False, "error": "UnregisteredError"},
            {"token_suffix": alive[-8:], "ok": True, "error": None},
        ]
        message = next(c.args[0] for c in fake_firebase.send.call_args_list if c.args[0].token == alive)
        assert message.notification.title == "Hola" and message.notification.body == "Cuerpo"
        assert message.data == {"type": "OTHER", "n": "1"}
        assert message.android.priority == "high"
        assert message.android.notification.channel_id == "skillmatch_notifications"
        async with _session() as db:
            assert await db.scalar(select(User.full_name).where(User.id == member.id)) == "Push Test"
            states = dict((await db.execute(
                select(DevicePushToken.fcm_token, DevicePushToken.is_active).where(DevicePushToken.user_id == member.id)
            )).all())
        assert states == {dead: False, alive: True}


@pytest.mark.parametrize("error,deactivated", [
    (messaging.SenderIdMismatchError("mismatch"), True),
    (firebase_exceptions.InvalidArgumentError("The registration token is not a valid FCM registration token"), True),
    (firebase_exceptions.UnavailableError("backend unavailable"), False),
])
async def test_send_deactivates_only_token_errors(fake_firebase, error, deactivated):
    fake_firebase.send.side_effect = error
    async with _members(tokens=1) as (users, token_values):
        token = token_values[users[0].id][0]
        async with _session() as caller:
            results = await FCMService.send_push_to_user(caller, user_id=users[0].id, title="t", body="b")
        assert results == [{"token_suffix": token[-8:], "ok": False, "error": type(error).__name__}]
        async with _session() as db:
            active = await db.scalar(select(DevicePushToken.is_active).where(DevicePushToken.fcm_token == token))
        assert active is (not deactivated)


async def test_send_without_firebase_reports_each_token_and_never_raises(fake_firebase):
    fake_firebase.certificate.side_effect = ValueError("broken")
    async with _members(tokens=1) as (users, token_values):
        token = token_values[users[0].id][0]
        async with _session() as caller:
            results = await FCMService.send_push_to_user(caller, user_id=users[0].id, title="t", body="b")
        assert results == [{"token_suffix": token[-8:], "ok": False, "error": "FIREBASE_NOT_INITIALIZED"}]
        fake_firebase.send.assert_not_called()


# ---------------------------------------------------------------- S4 post-commit dispatch

async def _emit(db, user_id, event_id=None, kind="POINTS_RECEIVED"):
    return await NotificationService.emit_in_app(
        db, user_id=user_id, event_id=event_id or uuid4(), notification_type=kind, title="Titulo", message="Mensaje",
    )


async def test_committed_new_notification_pushes_once_after_commit(fake_firebase):
    async with _members(push=True, tokens=1) as (users, token_values):
        member = users[0]
        async with _session() as db:
            item = await _emit(db, member.id)
            await asyncio.sleep(0)
            await notification_push_dispatcher.drain()
            fake_firebase.send.assert_not_called()  # nothing before commit
            await db.commit()
        await notification_push_dispatcher.drain()
        assert _sent_tokens(fake_firebase.send) == token_values[member.id]
        message = fake_firebase.send.call_args.args[0]
        assert message.data == {"type": "POINTS_RECEIVED", "notification_id": str(item.id)}
        assert message.notification.title == "Titulo" and message.notification.body == "Mensaje"


async def test_rolled_back_or_replayed_notifications_never_push(fake_firebase):
    async with _members(push=True, tokens=1) as (users, _tokens):
        member = users[0]
        async with _session() as db:
            await _emit(db, member.id)
            await db.rollback()
        async with _session() as db:
            savepoint = await db.begin_nested()
            await _emit(db, member.id)
            await savepoint.rollback()  # savepoint rollback discards the notice
            await db.commit()
        await notification_push_dispatcher.drain()
        assert fake_firebase.send.call_count == 0

        event = uuid4()
        async with _session() as db:
            await _emit(db, member.id, event)
            await db.commit()
        await notification_push_dispatcher.drain()
        assert fake_firebase.send.call_count == 1
        async with _session() as db:
            await _emit(db, member.id, event)  # replay of the same event
            await db.commit()
        await notification_push_dispatcher.drain()
        assert fake_firebase.send.call_count == 1


@pytest.mark.parametrize("prefs,kind,pushes", [
    (None, "POINTS_RECEIVED", 1),  # defaults: push toggle False, categories on -> push (L4)
    ({"push": False}, "MATCH_RECEIVED", 1),  # explicit push toggle off is not a gate
    ({"push": True, "points": False}, "POINTS_RECEIVED", 0),  # category off -> no push
    ({"push": True, "interchanges": False}, "MATCH_RECEIVED", 0),
    ({"push": True, "general": False, "in_app": True}, "OTHER", 0),
])
async def test_push_gate_is_the_category_flag_only(fake_firebase, prefs, kind, pushes):
    async with _members(push=None, tokens=1) as (users, _tokens):
        member = users[0]
        async with _session() as db:
            if prefs is not None:
                db.add(NotificationPreference(user_id=member.id, **prefs))
            await db.commit()
        async with _session() as db:
            # A disabled category also suppresses the in-app row itself, so nothing is recorded.
            await _emit(db, member.id, kind=kind)
            await db.commit()
        await notification_push_dispatcher.drain()
        assert fake_firebase.send.call_count == pushes


async def test_category_disabled_between_commit_and_dispatch_never_pushes(fake_firebase, monkeypatch):
    """The dispatcher re-reads the category flag in its own session (not the emitting snapshot)."""
    async with _members(push=None, tokens=1) as (users, _tokens):
        member = users[0]
        captured: list[notification_push_dispatcher.PendingPush] = []

        async def capture(item):
            captured.append(item)

        monkeypatch.setattr(notification_push_dispatcher, "dispatch_hook", capture)
        async with _session() as db:
            await _emit(db, member.id, kind="POINTS_RECEIVED")
            await db.commit()
        await notification_push_dispatcher.drain()
        async with _session() as db:
            db.add(NotificationPreference(user_id=member.id, points=False))
            await db.commit()
        await notification_push_dispatcher.dispatch_notification_push(captured[0])
        fake_firebase.send.assert_not_called()


async def test_after_commit_runs_inside_the_running_loop(fake_firebase, monkeypatch):
    """Empirical: get_running_loop() works in the greenlet-driven after_commit of an AsyncSession."""
    scheduled: list[int] = []
    real_schedule = notification_push_dispatcher.schedule_dispatch

    def spy(items):
        asyncio.get_running_loop()  # raises RuntimeError if no loop is visible here
        tasks = real_schedule(items)
        scheduled.append(len(tasks))
        return tasks

    monkeypatch.setattr(notification_push_dispatcher, "schedule_dispatch", spy)
    async with _members(push=None, tokens=1) as (users, _tokens):
        async with _session() as db:
            await _emit(db, users[0].id)
            await _emit(db, users[0].id)
            await db.commit()
        await notification_push_dispatcher.drain()
    assert scheduled == [2]
    assert fake_firebase.send.call_count == 2


async def test_dispatch_failure_never_breaks_the_commit(fake_firebase, monkeypatch):
    async def boom(_item):
        raise RuntimeError("dispatcher exploded")

    monkeypatch.setattr(notification_push_dispatcher, "dispatch_hook", boom)
    async with _members(push=True, tokens=1) as (users, _tokens):
        async with _session() as db:
            item = await _emit(db, users[0].id)
            await db.commit()
        await notification_push_dispatcher.drain()
        async with _session() as db:
            assert await db.scalar(select(Notification.id).where(Notification.id == item.id)) == item.id


# ---------------------------------------------------------------- S4 preserve: former ad-hoc producers

async def test_wallet_topup_pushes_exactly_once_after_commit(fake_firebase, monkeypatch):
    """Top-up kept its in-app notice; the removed ad-hoc FCM call no longer duplicates the push."""
    from app.schemas.wallet import TopupRequest
    from app.services import wallet_service as wallet_module

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(wallet_module.asyncio, "sleep", no_sleep)
    async with _members(tokens=1) as (users, token_values):
        member = users[0]
        async with _session() as db:
            result = await wallet_module.wallet_service.topup_wallet(
                db, member.id, TopupRequest(package_id="pkg_student", payment_method="card", card_last_four="4242"),
            )
        await notification_push_dispatcher.drain()
        assert result.total_points_added == 275
        assert _sent_tokens(fake_firebase.send) == token_values[member.id]
        message = fake_firebase.send.call_args.args[0]
        assert message.data["type"] == "POINTS_RECEIVED"
        assert message.notification.title == "Recarga de SkillPoints Exitosa"


async def test_session_counterpart_notice_pushes_once_to_the_counterpart(fake_firebase):
    from types import SimpleNamespace

    from app.services.exchange_session_service import _notify_counterpart

    async with _members(2, tokens=1) as (users, token_values):
        learner, instructor = users
        item = SimpleNamespace(id=uuid4(), learner_id=learner.id, instructor_id=instructor.id)
        async with _session() as db:
            await _notify_counterpart(db, item, learner.id, "SESSION_PROPOSED", "Nueva sesión", "Te propusieron una sesión")
            await notification_push_dispatcher.drain()
            fake_firebase.send.assert_not_called()  # nothing before the caller commits
            await db.commit()
        await notification_push_dispatcher.drain()
        assert _sent_tokens(fake_firebase.send) == token_values[instructor.id]
        assert fake_firebase.send.call_args.args[0].data["type"] == "SESSION_PROPOSED"


# ---------------------------------------------------------------- S5 admin diagnostics

def _auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user.id), user.role.value)}"}


@asynccontextmanager
async def _client():
    transport = httpx.ASGITransport(app=create_application())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


NOT_FOUND = {"statuscode": 404, "message": "Recurso no encontrado", "data": None}


@pytest.mark.parametrize("method,path", [("GET", "/api/admin/push/status"), ("POST", "/api/admin/push/test")])
async def test_admin_push_endpoints_are_obfuscated_for_anonymous_and_members(fake_firebase, method, path):
    async with _members() as (users, _tokens), _client() as client:
        anonymous = await client.request(method, path, json={})
        member = await client.request(method, path, json={}, headers=_auth(users[0]))
    for response in (anonymous, member):
        assert response.status_code == 404
        assert {k: response.json().get(k) for k in NOT_FOUND} == NOT_FOUND
    fake_firebase.send.assert_not_called()


async def test_admin_status_reports_firebase_and_device_counts(fake_firebase):
    async with _members(role=UserRole.ADMIN) as (admins, _), _members(tokens=2), _client() as client:
        response = await client.get("/api/admin/push/status", headers=_auth(admins[0]))
    body = response.json()
    assert response.status_code == 200 and body["statuscode"] == 200
    assert body["data"]["firebase"] == {"initialized": True, "source": "json", "error": None}
    devices = body["data"]["devices"]
    assert set(devices) == {"active", "total", "users_with_active"}
    assert devices["active"] >= 2 and devices["total"] >= devices["active"] and devices["users_with_active"] >= 1
    fake_firebase.initialize_app.assert_called_once()
    assert "FAKEKEYMATERIAL" not in response.text and "demo-test" not in response.text


async def test_admin_test_push_to_user_and_to_recent_devices(fake_firebase):
    async with _members(role=UserRole.ADMIN) as (admins, _), _members(tokens=2) as (members, token_values), _client() as client:
        member = members[0]
        tokens = token_values[member.id]
        response = await client.post(
            "/api/admin/push/test", headers=_auth(admins[0]),
            json={"user_id": str(member.id), "title": "Prueba", "body": "Hola"},
        )
        body = response.json()
        assert response.status_code == 200 and body["statuscode"] == 200
        assert body["data"]["sent"] == 2 and body["data"]["failed"] == 0
        assert sorted(r["token_suffix"] for r in body["data"]["results"]) == sorted(t[-8:] for t in tokens)
        assert all(r["user_id"] == str(member.id) and r["ok"] and r["error"] is None for r in body["data"]["results"])
        assert sorted(_sent_tokens(fake_firebase.send)) == sorted(tokens)
        assert fake_firebase.send.call_args.args[0].notification.title == "Prueba"

        fake_firebase.send.reset_mock()
        recent = await client.post("/api/admin/push/test", headers=_auth(admins[0]), json={})
        data = recent.json()["data"]
        assert recent.status_code == 200 and 1 <= len(data["results"]) <= 5
        assert data["sent"] + data["failed"] == len(data["results"]) == fake_firebase.send.call_count
        assert {t[-8:] for t in tokens} <= {r["token_suffix"] for r in data["results"]}
    for text in (response.text, recent.text):
        assert all(t not in text for t in tokens)
        assert "FAKEKEYMATERIAL" not in text
