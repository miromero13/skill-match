"""HU-38 behavior contracts for scheduled reminders and manual calendar export.

These tests intentionally precede the production implementation.
"""

from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse
from uuid import uuid4


def test_reminder_policy_emits_at_24_hours_and_1_hour_only() -> None:
    from app.services.session_reminder_policy import due_reminder_thresholds

    starts_at = datetime(2026, 12, 1, 18, tzinfo=UTC)

    assert due_reminder_thresholds(starts_at, starts_at - timedelta(hours=24)) == ("24H",)
    assert due_reminder_thresholds(starts_at, starts_at - timedelta(hours=1)) == ("1H",)
    assert due_reminder_thresholds(starts_at, starts_at - timedelta(hours=12)) == ()


def test_reminder_policy_accepts_a_short_scheduler_delay_but_not_an_old_window() -> None:
    from app.services.session_reminder_policy import due_reminder_thresholds

    starts_at = datetime(2026, 12, 1, 18, tzinfo=UTC)
    lookback = timedelta(minutes=5)

    assert due_reminder_thresholds(
        starts_at,
        starts_at - timedelta(hours=24) + timedelta(minutes=4),
        lookback=lookback,
    ) == ("24H",)
    assert due_reminder_thresholds(
        starts_at,
        starts_at - timedelta(hours=24) + timedelta(minutes=6),
        lookback=lookback,
    ) == ()
    assert due_reminder_thresholds(
        starts_at,
        starts_at - timedelta(hours=24) - timedelta(seconds=1),
        lookback=lookback,
    ) == ()


def test_only_accepted_future_sessions_are_reminder_eligible() -> None:
    from app.services.session_reminder_policy import is_reminder_eligible

    now = datetime(2026, 12, 1, 17, tzinfo=UTC)

    assert is_reminder_eligible("ACCEPTED", now + timedelta(hours=1), now) is True
    for status in ("PENDING", "REJECTED", "CANCELLED"):
        assert is_reminder_eligible(status, now + timedelta(hours=1), now) is False
    assert is_reminder_eligible("ACCEPTED", now, now) is False
    assert is_reminder_eligible("ACCEPTED", now - timedelta(seconds=1), now) is False


def test_reminder_identity_is_stable_and_changes_after_reschedule() -> None:
    from app.services.session_reminder_policy import is_reminder_current, reminder_event_id

    session_id = uuid4()
    recipient_id = uuid4()
    first_start = datetime(2026, 12, 1, 18, tzinfo=UTC)
    moved_start = first_start + timedelta(days=1)

    first = reminder_event_id(session_id, recipient_id, "24H", first_start)
    assert first == reminder_event_id(session_id, recipient_id, "24H", first_start)
    assert first != reminder_event_id(session_id, recipient_id, "1H", first_start)
    assert first != reminder_event_id(session_id, recipient_id, "24H", moved_start)
    assert is_reminder_current(first_start, first_start, "ACCEPTED") is True
    assert is_reminder_current(first_start, moved_start, "ACCEPTED") is False
    assert is_reminder_current(first_start, first_start, "CANCELLED") is False
    assert is_reminder_current(first_start, first_start, "REJECTED") is False


def test_dispatch_contract_is_idempotent_for_both_participants() -> None:
    from app.services.session_reminder_service import build_reminder_emissions

    session_id = uuid4()
    instructor_id = uuid4()
    learner_id = uuid4()
    starts_at = datetime(2026, 12, 1, 18, tzinfo=UTC)

    first = build_reminder_emissions(
        session_id=session_id,
        instructor_id=instructor_id,
        learner_id=learner_id,
        starts_at=starts_at,
        threshold="24H",
    )
    retry = build_reminder_emissions(
        session_id=session_id,
        instructor_id=instructor_id,
        learner_id=learner_id,
        starts_at=starts_at,
        threshold="24H",
    )

    assert first == retry
    assert {item.user_id for item in first} == {instructor_id, learner_id}
    assert len({item.event_id for item in first}) == 2
    assert all(item.notification_type.value == "SESSION_REMINDER" for item in first)


def test_ics_export_is_rfc5545_shaped_utc_and_safely_escaped() -> None:
    from app.services.session_calendar_service import (
        build_ics_export,
        is_calendar_export_allowed,
    )

    session_id = uuid4()
    result = build_ics_export(
        session_id=session_id,
        starts_at=datetime(2026, 12, 1, 18, tzinfo=UTC),
        ends_at=datetime(2026, 12, 1, 19, tzinfo=UTC),
        timezone="America/La_Paz",
        skill_name="Guitarra, nivel 4",
        counterpart_name="Ana; Pérez",
        modality="VIRTUAL",
    )

    assert result.filename == f"skillmatch-session-{session_id}.ics"
    assert result.content_type == "text/calendar; charset=utf-8"
    assert "\r\n" in result.ics_content
    assert result.ics_content.startswith("BEGIN:VCALENDAR\r\n")
    assert result.ics_content.endswith("END:VCALENDAR\r\n")
    assert f"UID:{session_id}@skillmatch" in result.ics_content
    assert "DTSTART:20261201T180000Z" in result.ics_content
    assert "DTEND:20261201T190000Z" in result.ics_content
    assert "Guitarra\\, nivel 4" in result.ics_content
    assert "Ana\\; Pérez" in result.ics_content
    assert is_calendar_export_allowed("ACCEPTED") is True
    for status in ("PENDING", "REJECTED", "CANCELLED"):
        assert is_calendar_export_allowed(status) is False


def test_google_calendar_link_contains_the_same_canonical_event() -> None:
    from app.services.session_calendar_service import build_google_calendar_url

    url = build_google_calendar_url(
        starts_at=datetime(2026, 12, 1, 18, tzinfo=UTC),
        ends_at=datetime(2026, 12, 1, 19, tzinfo=UTC),
        timezone="America/La_Paz",
        skill_name="Guitarra clásica",
        counterpart_name="Ana Pérez",
        modality="VIRTUAL",
    )
    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert parsed.netloc == "calendar.google.com"
    assert parsed.path == "/calendar/render"
    assert query["action"] == ["TEMPLATE"]
    assert query["dates"] == ["20261201T180000Z/20261201T190000Z"]
    assert query["text"] == ["SkillMatch · Guitarra clásica"]
    assert query["ctz"] == ["America/La_Paz"]
    assert "Ana Pérez" in query["details"][0]


def test_calendar_export_route_is_documented_with_apiresponse() -> None:
    from app.api.sessions import current_member
    from app.main import create_application

    app = create_application()
    operation = app.openapi()["paths"][
        "/api/sessions/{session_id}/calendar-export"
    ]["get"]

    assert operation["responses"]["200"]["content"]["application/json"]
    included = next(
        item
        for item in app.routes
        if getattr(item, "original_router", None) is not None
        and any(
            getattr(route, "path", None) == "/sessions/{session_id}/calendar-export"
            for route in item.original_router.routes
        )
    )
    route = next(
        route
        for route in included.original_router.routes
        if getattr(route, "path", None) == "/sessions/{session_id}/calendar-export"
    )
    assert any(dependency.call is current_member for dependency in route.dependant.dependencies)
