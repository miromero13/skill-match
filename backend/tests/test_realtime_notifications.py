"""HU-24 test-first contract for authenticated realtime notifications.

Production modules are intentionally imported inside tests so the red phase is
reported as missing HU-24 behavior instead of preventing test collection.
"""
from datetime import datetime, timezone
import asyncio
from importlib import import_module
from types import SimpleNamespace
from uuid import uuid4

import pytest
from jose import jwt
from pydantic import ValidationError

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token
from app.main import create_application
from test_notifications import inbox  # noqa: F401 - shared real JWT/DB fixture

pytestmark = pytest.mark.hu24
TICKET_PATH = "/api/notifications/ws-token"
SOCKET_PATH = "/ws/notifications"
KINDS = ["MATCH_RECEIVED", "MATCH_CONFIRMED", "SESSION_PROPOSED", "POINTS_RECEIVED"]


def hu24_module(name: str):
    return import_module(name)


def notification_data(kind: str = "MATCH_RECEIVED", message: str = "Mensaje exacto") -> dict:
    categories = {
        "MATCH_RECEIVED": "INTERCHANGES",
        "MATCH_CONFIRMED": "INTERCHANGES",
        "SESSION_PROPOSED": "INTERCHANGES",
        "POINTS_RECEIVED": "POINTS",
    }
    return {
        "id": uuid4(),
        "type": kind,
        "category": categories[kind],
        "title": "Aviso",
        "message": message,
        "created_at": datetime.now(timezone.utc),
        "read_at": None,
    }


def test_ticket_endpoint_is_documented_with_canonical_responses():
    paths = create_application().openapi()["paths"]
    assert TICKET_PATH in paths
    operation = paths[TICKET_PATH]["get"]
    assert {"200", "401", "403", "423"} <= operation["responses"].keys()
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]


def test_websocket_route_is_registered_outside_api_prefix():
    routes = []
    for candidate in create_application().routes:
        nested = getattr(candidate, "original_router", None)
        candidates = nested.routes if nested is not None else [candidate]
        routes.extend(route for route in candidates if getattr(route, "path", None) == SOCKET_PATH)
    assert len(routes) == 1
    assert routes[0].__class__.__name__ == "APIWebSocketRoute"


def test_ticket_ttl_is_explicit_and_bounded():
    assert settings.WS_TICKET_EXPIRE_SECONDS == 30
    field = settings.__class__.model_fields["WS_TICKET_EXPIRE_SECONDS"]
    assert field.annotation is int


@pytest.mark.parametrize("role", ["MEMBER", "ADMIN"])
def test_ticket_roundtrip_has_dedicated_type_and_identity(role):
    service = hu24_module("app.services.websocket_ticket_service").WebSocketTicketService
    user_id = uuid4()
    ticket = service.issue(user_id=user_id, role=role)
    identity = service.validate(ticket)
    claims = jwt.decode(
        ticket,
        settings.SECRET_KEY.get_secret_value(),
        algorithms=[settings.ALGORITHM],
    )
    assert identity.user_id == user_id
    assert identity.role == role
    assert claims["sub"] == str(user_id)
    assert claims["role"] == role
    assert claims["type"] == "websocket"
    assert isinstance(claims["jti"], str) and claims["jti"]
    assert 0 < claims["exp"] - claims["iat"] <= settings.WS_TICKET_EXPIRE_SECONDS


@pytest.mark.parametrize("role", ["OWNER", "USER", "", None])
def test_ticket_rejects_noncanonical_roles(role):
    service = hu24_module("app.services.websocket_ticket_service").WebSocketTicketService
    with pytest.raises(ValueError):
        service.issue(user_id=uuid4(), role=role)


def test_websocket_validator_rejects_access_and_refresh_tokens():
    service = hu24_module("app.services.websocket_ticket_service").WebSocketTicketService
    user_id = uuid4()
    tokens = [
        create_access_token(str(user_id), "MEMBER"),
        create_refresh_token(str(user_id), "MEMBER"),
    ]
    for token in tokens:
        with pytest.raises(Exception):
            service.validate(token)


def test_websocket_validator_rejects_expired_ticket():
    service = hu24_module("app.services.websocket_ticket_service").WebSocketTicketService
    now = int(datetime.now(timezone.utc).timestamp())
    expired = jwt.encode(
        {
            "sub": str(uuid4()),
            "role": "MEMBER",
            "type": "websocket",
            "iat": now - 60,
            "exp": now - 30,
            "jti": str(uuid4()),
        },
        settings.SECRET_KEY.get_secret_value(),
        algorithm=settings.ALGORITHM,
    )
    with pytest.raises(Exception):
        service.validate(expired)


@pytest.mark.parametrize("ticket", ["", "invalid", "a.b.c"])
def test_websocket_validator_rejects_malformed_tickets(ticket):
    service = hu24_module("app.services.websocket_ticket_service").WebSocketTicketService
    with pytest.raises(Exception):
        service.validate(ticket)


@pytest.mark.parametrize("kind", KINDS)
def test_event_schema_accepts_required_types_and_exact_message(kind):
    schema = hu24_module("app.schemas.realtime_notification").RealtimeNotificationEvent
    event = schema(
        event="notification.created",
        message="Mensaje exacto",
        data=notification_data(kind),
    )
    dumped = event.model_dump(mode="json")
    assert dumped["event"] == "notification.created"
    assert dumped["message"] == dumped["data"]["message"]
    assert dumped["data"]["type"] == kind


def test_event_schema_rejects_message_mismatch_and_extra_fields():
    schema = hu24_module("app.schemas.realtime_notification").RealtimeNotificationEvent
    with pytest.raises(ValidationError):
        schema(event="notification.created", message="Otro", data=notification_data())
    with pytest.raises(ValidationError):
        schema(
            event="notification.created",
            message="Mensaje exacto",
            data=notification_data(),
            user_id=uuid4(),
        )


class FakeSocket:
    def __init__(self, *, fail=False):
        self.accepted = 0
        self.sent: list[dict] = []
        self.closed: list[int] = []
        self.fail = fail

    async def accept(self):
        self.accepted += 1

    async def send_json(self, payload):
        if self.fail:
            raise RuntimeError("socket disconnected")
        self.sent.append(payload)

    async def close(self, code=1000):
        self.closed.append(code)


async def test_manager_fans_out_only_to_the_recipient_and_supports_many_tabs():
    manager_type = hu24_module(
        "app.services.notification_connection_manager"
    ).NotificationConnectionManager
    manager = manager_type()
    owner, stranger = uuid4(), uuid4()
    owner_a, owner_b, other = FakeSocket(), FakeSocket(), FakeSocket()
    await manager.connect(owner, owner_a)
    await manager.connect(owner, owner_b)
    await manager.connect(stranger, other)
    payload = {"event": "notification.created", "message": "M", "data": {"id": str(uuid4())}}
    delivered = await manager.publish(owner, payload)
    assert delivered == 2
    assert owner_a.sent == owner_b.sent == [payload]
    assert other.sent == []
    assert manager.connection_count(owner) == 2
    assert manager.connection_count(stranger) == 1


async def test_manager_disconnect_is_idempotent_and_removes_dead_sockets():
    manager_type = hu24_module(
        "app.services.notification_connection_manager"
    ).NotificationConnectionManager
    manager = manager_type()
    owner = uuid4()
    alive, dead = FakeSocket(), FakeSocket(fail=True)
    await manager.connect(owner, alive)
    await manager.connect(owner, dead)
    await manager.publish(owner, {"event": "notification.created", "message": "M", "data": {}})
    assert manager.connection_count(owner) == 1
    await manager.disconnect(owner, alive)
    await manager.disconnect(owner, alive)
    assert manager.connection_count(owner) == 0


async def test_manager_shutdown_closes_every_socket_and_clears_registry():
    manager_type = hu24_module(
        "app.services.notification_connection_manager"
    ).NotificationConnectionManager
    manager = manager_type()
    first_user, second_user = uuid4(), uuid4()
    first, second = FakeSocket(), FakeSocket()
    await manager.connect(first_user, first)
    await manager.connect(second_user, second)
    await manager.close_all()
    assert first.closed == second.closed == [1001]
    assert manager.connection_count(first_user) == 0
    assert manager.connection_count(second_user) == 0


async def test_ticket_endpoint_uses_apiresponse_and_never_returns_count(inbox):
    response = await inbox.client.get(TICKET_PATH, headers=inbox.headers[0])
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"statuscode", "message", "data"}
    assert body["statuscode"] == 200
    assert body["message"] == "Ticket WebSocket generado exitosamente."
    assert body["data"]["expires_in"] == 30
    assert body["data"]["websocket_path"] == SOCKET_PATH
    assert isinstance(body["data"]["ticket"], str) and body["data"]["ticket"]


async def test_ticket_endpoint_requires_access_authentication(inbox):
    anonymous = await inbox.client.get(TICKET_PATH)
    refresh = create_refresh_token(str(inbox.users[0].id), inbox.users[0].role)
    wrong_type = await inbox.client.get(
        TICKET_PATH,
        headers={"Authorization": f"Bearer {refresh}"},
    )
    assert anonymous.status_code == 401
    assert wrong_type.status_code == 401
    for response in [anonymous, wrong_type]:
        assert set(response.json()) == {"statuscode", "message", "data"}
        assert response.json()["data"] is None


@pytest.mark.parametrize(("attribute", "value", "status"), [
    ("is_active", False, 403),
    ("is_locked", True, 423),
])
async def test_ticket_endpoint_rejects_ineligible_accounts(inbox, attribute, value, status):
    setattr(inbox.users[0], attribute, value)
    await inbox.db.commit()
    response = await inbox.client.get(TICKET_PATH, headers=inbox.headers[0])
    assert response.status_code == status
    assert set(response.json()) == {"statuscode", "message", "data"}
    assert response.json()["data"] is None


def test_control_contract_is_strict_and_bounded():
    schema = hu24_module("app.schemas.realtime_notification").WebSocketClientMessage
    assert schema(event="ping").model_dump() == {"event": "ping"}
    with pytest.raises(ValidationError):
        schema(event="publish", user_id=str(uuid4()))
    with pytest.raises(ValidationError):
        schema(event="x" * 1025)


class FakeDatabase:
    def __init__(self, user):
        self.user = user

    async def scalar(self, _statement):
        return self.user

    async def close(self):
        """Match the session lifecycle used during the WebSocket handshake."""
        pass


def websocket_test_client(user):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.notifications.websocket import router
    from app.db.session import get_db

    application = FastAPI()
    application.include_router(router)

    async def override_db():
        yield FakeDatabase(user)

    application.dependency_overrides[get_db] = override_db
    return TestClient(application)


def test_websocket_handshake_accepts_member_and_answers_ping():
    from app.services.notification_connection_manager import notification_connection_manager
    from app.services.websocket_ticket_service import WebSocketTicketService

    user_id = uuid4()
    user = SimpleNamespace(id=user_id, role="MEMBER", is_active=True, is_locked=False)
    ticket = WebSocketTicketService.issue(user_id=user_id, role="MEMBER")
    with websocket_test_client(user) as client:
        with client.websocket_connect(f"{SOCKET_PATH}?ticket={ticket}") as websocket:
            assert notification_connection_manager.connection_count(user_id) == 1
            websocket.send_json({"event": "ping"})
            assert websocket.receive_json() == {"event": "pong"}
    assert notification_connection_manager.connection_count(user_id) == 0


@pytest.mark.parametrize(("ticket", "expected_code"), [(None, 1008), ("invalid", 1008)])
def test_websocket_handshake_rejects_missing_or_invalid_ticket(ticket, expected_code):
    from starlette.websockets import WebSocketDisconnect

    user = SimpleNamespace(id=uuid4(), role="MEMBER", is_active=True, is_locked=False)
    path = SOCKET_PATH if ticket is None else f"{SOCKET_PATH}?ticket={ticket}"
    with websocket_test_client(user) as client:
        with pytest.raises(WebSocketDisconnect) as failure:
            with client.websocket_connect(path):
                pass
    assert failure.value.code == expected_code


@pytest.mark.parametrize("changes", [
    {"role": "ADMIN"},
    {"is_active": False},
    {"is_locked": True},
])
def test_websocket_handshake_rejects_role_mismatch_or_ineligible_user(changes):
    from starlette.websockets import WebSocketDisconnect

    from app.services.websocket_ticket_service import WebSocketTicketService

    user_id = uuid4()
    values = {"id": user_id, "role": "MEMBER", "is_active": True, "is_locked": False, **changes}
    user = SimpleNamespace(**values)
    ticket = WebSocketTicketService.issue(user_id=user_id, role="MEMBER")
    with websocket_test_client(user) as client:
        with pytest.raises(WebSocketDisconnect) as failure:
            with client.websocket_connect(f"{SOCKET_PATH}?ticket={ticket}"):
                pass
    assert failure.value.code == 1008


def test_websocket_handshake_rejects_deleted_user():
    from starlette.websockets import WebSocketDisconnect

    from app.services.websocket_ticket_service import WebSocketTicketService

    user_id = uuid4()
    ticket = WebSocketTicketService.issue(user_id=user_id, role="MEMBER")
    with websocket_test_client(None) as client:
        with pytest.raises(WebSocketDisconnect) as failure:
            with client.websocket_connect(f"{SOCKET_PATH}?ticket={ticket}"):
                pass
    assert failure.value.code == 1008


@pytest.mark.parametrize(("payload", "expected_code"), [
    ({"event": "publish"}, 1008),
    ({"event": "x" * 1025}, 1009),
])
def test_websocket_rejects_domain_commands_and_oversized_input(payload, expected_code):
    from starlette.websockets import WebSocketDisconnect

    from app.services.websocket_ticket_service import WebSocketTicketService

    user_id = uuid4()
    user = SimpleNamespace(id=user_id, role="MEMBER", is_active=True, is_locked=False)
    ticket = WebSocketTicketService.issue(user_id=user_id, role="MEMBER")
    with websocket_test_client(user) as client:
        with client.websocket_connect(f"{SOCKET_PATH}?ticket={ticket}") as websocket:
            websocket.send_json(payload)
            with pytest.raises(WebSocketDisconnect) as failure:
                websocket.receive_json()
    assert failure.value.code == expected_code


@pytest.fixture
async def durable_notification():
    from sqlalchemy import delete
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.core.config import settings
    from app.models.notification import Notification
    from app.models.user import User

    engine = create_async_engine(settings.async_database_url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    user_id, notification_id = uuid4(), uuid4()
    async with session_factory() as db:
        db.add(User(
            id=user_id,
            email=f"hu24-durable-{user_id}@example.invalid",
            full_name="HU24 Durable",
            role="MEMBER",
        ))
        await db.flush()
        db.add(Notification(
            id=notification_id,
            event_id=uuid4(),
            user_id=user_id,
            type="MATCH_RECEIVED",
            title="Nuevo match",
            message="Mensaje durable",
        ))
        await db.commit()
    try:
        yield SimpleNamespace(
            user_id=user_id,
            notification_id=notification_id,
            session_factory=session_factory,
        )
    finally:
        async with session_factory() as db:
            await db.execute(delete(User).where(User.id == user_id))
            await db.commit()
        await engine.dispose()


async def test_committed_notification_is_published_once_with_canonical_envelope(durable_notification):
    from app.services.notification_connection_manager import NotificationConnectionManager
    from app.services.realtime_notification_publisher import RealtimeNotificationPublisher

    manager = NotificationConnectionManager()
    socket = FakeSocket()
    await manager.connect(durable_notification.user_id, socket)
    publisher = RealtimeNotificationPublisher(
        manager=manager,
        session_factory=durable_notification.session_factory,
    )
    first = await publisher.publish_committed(durable_notification.notification_id)
    second = await publisher.publish_committed(durable_notification.notification_id)
    assert first == 1 and second == 0
    assert len(socket.sent) == 1
    payload = socket.sent[0]
    assert payload["event"] == "notification.created"
    assert payload["message"] == payload["data"]["message"] == "Mensaje durable"
    assert payload["data"]["id"] == str(durable_notification.notification_id)
    assert "user_id" not in payload["data"] and "event_id" not in payload["data"]


async def test_uncommitted_notification_is_never_visible_to_publisher():
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.core.config import settings
    from app.models.notification import Notification
    from app.models.user import User
    from app.services.notification_connection_manager import NotificationConnectionManager
    from app.services.realtime_notification_publisher import RealtimeNotificationPublisher

    manager = NotificationConnectionManager()
    socket = FakeSocket()
    user_id, notification_id = uuid4(), uuid4()
    await manager.connect(user_id, socket)
    engine = create_async_engine(settings.async_database_url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    publisher = RealtimeNotificationPublisher(manager=manager, session_factory=session_factory)
    async with session_factory() as producer:
        producer.add(User(
            id=user_id,
            email=f"hu24-rollback-{user_id}@example.invalid",
            full_name="HU24 Rollback",
            role="MEMBER",
        ))
        await producer.flush()
        producer.add(Notification(
            id=notification_id,
            event_id=uuid4(),
            user_id=user_id,
            type="MATCH_CONFIRMED",
            title="Confirmado",
            message="No debe salir",
        ))
        await producer.flush()
        assert await publisher.publish_committed(notification_id) == 0
        await producer.rollback()
    assert socket.sent == []
    await engine.dispose()


async def test_deleted_notification_is_not_published(durable_notification):
    from sqlalchemy import update

    from app.models.notification import Notification
    from app.services.notification_connection_manager import NotificationConnectionManager
    from app.services.realtime_notification_publisher import RealtimeNotificationPublisher

    async with durable_notification.session_factory() as db:
        await db.execute(update(Notification).where(
            Notification.id == durable_notification.notification_id,
        ).values(deleted_at=datetime.now(timezone.utc)))
        await db.commit()
    manager = NotificationConnectionManager()
    socket = FakeSocket()
    await manager.connect(durable_notification.user_id, socket)
    publisher = RealtimeNotificationPublisher(
        manager=manager,
        session_factory=durable_notification.session_factory,
    )
    assert await publisher.publish_committed(durable_notification.notification_id) == 0
    assert socket.sent == []


async def test_concurrent_publish_claims_one_delivery(durable_notification):
    from app.services.notification_connection_manager import NotificationConnectionManager
    from app.services.realtime_notification_publisher import RealtimeNotificationPublisher

    manager = NotificationConnectionManager()
    socket = FakeSocket()
    await manager.connect(durable_notification.user_id, socket)
    publisher = RealtimeNotificationPublisher(
        manager=manager,
        session_factory=durable_notification.session_factory,
    )
    results = await asyncio.gather(*(
        publisher.publish_committed(durable_notification.notification_id)
        for _ in range(8)
    ))
    assert results.count(1) == 1
    assert results.count(0) == 7
    assert len(socket.sent) == 1
