"""Test-first contracts for HU-38 Web Push delivery policy."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest


def test_push_payload_opens_the_sessions_page_without_private_data() -> None:
    from app.services.session_web_push_service import build_session_reminder_push

    event_id = uuid4()
    payload = build_session_reminder_push(event_id=event_id, threshold="1H")

    assert payload.title == "Recordatorio de sesión"
    assert payload.body == "Tu sesión de intercambio comienza en 1 hora."
    assert payload.url == "/app/sessions"
    assert payload.event_id == event_id
    serialized = payload.to_json()
    assert "@" not in serialized
    assert "token" not in serialized.lower()
    assert "address" not in serialized.lower()


def test_push_delivery_identity_is_stable_per_event_and_device() -> None:
    from app.services.session_web_push_service import web_push_delivery_identity

    event_id = uuid4()
    first_device = uuid4()
    second_device = uuid4()

    first = web_push_delivery_identity(event_id, first_device)
    assert first == web_push_delivery_identity(event_id, first_device)
    assert first != web_push_delivery_identity(event_id, second_device)
    assert first != web_push_delivery_identity(uuid4(), first_device)


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (404, "EXPIRED"),
        (410, "EXPIRED"),
        (429, "TRANSIENT"),
        (500, "TRANSIENT"),
        (503, "TRANSIENT"),
        (400, "PERMANENT"),
        (401, "CONFIGURATION"),
        (403, "CONFIGURATION"),
    ],
)
def test_web_push_http_errors_have_explicit_retry_policy(
    status_code: int,
    expected: str,
) -> None:
    from app.services.session_web_push_service import classify_web_push_status

    assert classify_web_push_status(status_code).value == expected


def test_expired_subscription_is_deactivated_and_transient_failure_is_bounded() -> None:
    from app.services.session_web_push_service import resolve_web_push_outcome

    expired = resolve_web_push_outcome(status_code=410, attempt_count=1)
    assert expired.delivery_status == "SKIPPED"
    assert expired.subscription_active is False
    assert expired.retry is False

    throttled = resolve_web_push_outcome(status_code=429, attempt_count=1)
    assert throttled.delivery_status == "PENDING"
    assert throttled.subscription_active is True
    assert throttled.retry is True

    exhausted = resolve_web_push_outcome(status_code=503, attempt_count=3)
    assert exhausted.delivery_status == "FAILED"
    assert exhausted.subscription_active is True
    assert exhausted.retry is False


def test_push_eligibility_requires_preference_active_subscription_and_current_session() -> None:
    from app.services.session_web_push_service import is_web_push_delivery_eligible

    now = datetime(2026, 12, 1, 17, tzinfo=UTC)
    starts_at = now + timedelta(hours=1)

    assert is_web_push_delivery_eligible(
        preference_enabled=True,
        subscription_active=True,
        session_status="ACCEPTED",
        expected_starts_at=starts_at,
        current_starts_at=starts_at,
        now=now,
    ) is True
    assert is_web_push_delivery_eligible(
        preference_enabled=False,
        subscription_active=True,
        session_status="ACCEPTED",
        expected_starts_at=starts_at,
        current_starts_at=starts_at,
        now=now,
    ) is False
    assert is_web_push_delivery_eligible(
        preference_enabled=True,
        subscription_active=False,
        session_status="ACCEPTED",
        expected_starts_at=starts_at,
        current_starts_at=starts_at,
        now=now,
    ) is False


@pytest.mark.parametrize("terminal_status", ["PENDING", "REJECTED", "CANCELLED"])
def test_push_is_invalidated_by_non_accepted_session(terminal_status: str) -> None:
    from app.services.session_web_push_service import is_web_push_delivery_eligible

    now = datetime(2026, 12, 1, 17, tzinfo=UTC)
    starts_at = now + timedelta(hours=1)
    assert is_web_push_delivery_eligible(
        preference_enabled=True,
        subscription_active=True,
        session_status=terminal_status,
        expected_starts_at=starts_at,
        current_starts_at=starts_at,
        now=now,
    ) is False


def test_push_is_invalidated_after_reschedule_or_session_start() -> None:
    from app.services.session_web_push_service import is_web_push_delivery_eligible

    now = datetime(2026, 12, 1, 17, tzinfo=UTC)
    original = now + timedelta(hours=1)
    moved = original + timedelta(days=1)
    assert is_web_push_delivery_eligible(
        preference_enabled=True,
        subscription_active=True,
        session_status="ACCEPTED",
        expected_starts_at=original,
        current_starts_at=moved,
        now=now,
    ) is False
    assert is_web_push_delivery_eligible(
        preference_enabled=True,
        subscription_active=True,
        session_status="ACCEPTED",
        expected_starts_at=original,
        current_starts_at=original,
        now=original,
    ) is False


def test_subscription_schema_rejects_insecure_or_incomplete_capability_urls() -> None:
    from pydantic import ValidationError

    from app.schemas.web_push import WebPushSubscriptionCreate

    valid = {
        "endpoint": "https://push.example.test/send/device-one",
        "keys": {"p256dh": "public-key", "auth": "auth-secret"},
        "device_label": "Chrome desktop",
    }
    assert WebPushSubscriptionCreate.model_validate(valid).endpoint.startswith("https://")
    with pytest.raises(ValidationError):
        WebPushSubscriptionCreate.model_validate({**valid, "endpoint": "http://push.example.test/x"})
    with pytest.raises(ValidationError):
        WebPushSubscriptionCreate.model_validate({**valid, "keys": {"p256dh": "public-key"}})
    with pytest.raises(ValidationError):
        WebPushSubscriptionCreate.model_validate({**valid, "user_id": str(uuid4())})


def test_push_routes_are_protected_and_documented_with_apiresponse() -> None:
    from app.core.deps import get_current_user
    from app.main import create_application

    app = create_application()
    expected = {
        "/api/notifications/push/public-key": "get",
        "/api/notifications/push/subscriptions": "post",
        "/api/notifications/push/subscriptions/{subscription_id}": "delete",
    }
    schema = app.openapi()["paths"]
    for path, method in expected.items():
        operation = schema[path][method]
        assert operation["responses"]["200" if method != "post" else "201"]["content"]["application/json"]
        included = next(
            item
            for item in app.routes
            if getattr(item, "original_router", None) is not None
            and any(
                getattr(route, "path", None) == path.removeprefix("/api")
                and method.upper() in getattr(route, "methods", set())
                for route in item.original_router.routes
            )
        )
        route = next(
            route
            for route in included.original_router.routes
            if getattr(route, "path", None) == path.removeprefix("/api")
            and method.upper() in getattr(route, "methods", set())
        )
        assert any(dependency.call is get_current_user for dependency in route.dependant.dependencies)
