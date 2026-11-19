"""HU-38 behavior contract written before production implementation."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError


def valid_create_payload() -> dict:
    starts_at = datetime.now(UTC) + timedelta(days=3)
    return {
        "match_id": uuid4(),
        "teaching_skill_id": uuid4(),
        "instructor_id": uuid4(),
        "starts_at": starts_at,
        "ends_at": starts_at + timedelta(minutes=60),
        "timezone": "America/La_Paz",
        "modality": "VIRTUAL",
    }


def test_hu38_routes_are_registered_in_openapi():
    from app.main import create_application

    paths = create_application().openapi()["paths"]
    expected = {
        "/api/sessions": {"get", "post"},
        "/api/matches/{match_id}/session-options": {"get"},
        "/api/sessions/{session_id}/cancel": {"post"},
        "/api/sessions/{session_id}/reschedule": {"put"},
        "/api/sessions/{session_id}/status": {"patch"},
    }
    for path, methods in expected.items():
        assert path in paths
        assert methods <= set(paths[path])


def test_session_options_contract_is_strict_and_documents_the_horizon():
    from app.schemas.match import MatchSessionOptionsResponse

    payload = MatchSessionOptionsResponse(
        match_id=uuid4(),
        timezone="America/La_Paz",
        directions=[],
    )
    assert payload.horizon_days == 14
    assert payload.booking_blocked_until is None


def test_create_contract_accepts_the_ratified_payload():
    from app.schemas.exchange_session import ExchangeSessionCreate

    payload = valid_create_payload()
    parsed = ExchangeSessionCreate.model_validate(payload)
    assert parsed.match_id == payload["match_id"]
    assert parsed.teaching_skill_id == payload["teaching_skill_id"]
    assert parsed.instructor_id == payload["instructor_id"]
    assert parsed.modality == "VIRTUAL"
    assert parsed.timezone == "America/La_Paz"


@pytest.mark.parametrize("minutes", [0, 61, 120])
def test_create_contract_rejects_duration_outside_one_to_sixty_minutes(minutes: int):
    from app.schemas.exchange_session import ExchangeSessionCreate

    payload = valid_create_payload()
    payload["ends_at"] = payload["starts_at"] + timedelta(minutes=minutes)
    with pytest.raises(ValidationError):
        ExchangeSessionCreate.model_validate(payload)


@pytest.mark.parametrize("modality", ["BOTH", "IN_PERSON", "REMOTE", ""])
def test_create_contract_only_accepts_concrete_canonical_modalities(modality: str):
    from app.schemas.exchange_session import ExchangeSessionCreate

    payload = valid_create_payload() | {"modality": modality}
    with pytest.raises(ValidationError):
        ExchangeSessionCreate.model_validate(payload)


def test_create_contract_rejects_unknown_timezone():
    from app.schemas.exchange_session import ExchangeSessionCreate

    with pytest.raises(ValidationError):
        ExchangeSessionCreate.model_validate(valid_create_payload() | {"timezone": "Mars/Olympus"})


@pytest.mark.parametrize("reason", ["", "   ", "corto", "x" * 501])
def test_cancel_contract_requires_a_trimmed_reason_between_10_and_500(reason: str):
    from app.schemas.exchange_session import ExchangeSessionCancel

    with pytest.raises(ValidationError):
        ExchangeSessionCancel.model_validate({"cancellation_reason": reason})


def test_status_contract_reserves_completed_for_hu39():
    from app.schemas.exchange_session import ExchangeSessionStatusUpdate

    assert ExchangeSessionStatusUpdate(status="ACCEPTED").status == "ACCEPTED"
    assert ExchangeSessionStatusUpdate(status="REJECTED").status == "REJECTED"
    with pytest.raises(ValidationError):
        ExchangeSessionStatusUpdate(status="COMPLETED")


def test_local_week_is_monday_to_monday_in_learners_timezone():
    from app.services.exchange_session_policy import local_week_bounds

    instant = datetime(2026, 11, 22, 23, 30, tzinfo=UTC)
    start, end = local_week_bounds(instant, "America/La_Paz")
    local = ZoneInfo("America/La_Paz")
    assert start.astimezone(local).isoformat() == "2026-11-16T00:00:00-04:00"
    assert end.astimezone(local).isoformat() == "2026-11-23T00:00:00-04:00"
    assert end - start == timedelta(days=7)


def test_local_week_keeps_local_midnight_across_daylight_saving_change():
    from app.services.exchange_session_policy import local_week_bounds

    start, end = local_week_bounds(
        datetime(2026, 3, 8, 12, tzinfo=UTC),
        "America/New_York",
    )
    local = ZoneInfo("America/New_York")
    assert start.astimezone(local).isoformat() == "2026-03-02T00:00:00-05:00"
    assert end.astimezone(local).isoformat() == "2026-03-09T00:00:00-04:00"
    assert end - start == timedelta(hours=167)


def test_local_month_bounds_use_the_actor_timezone_and_cross_year():
    from app.services.exchange_session_policy import local_month_bounds

    start, end = local_month_bounds(
        datetime(2027, 1, 1, 2, tzinfo=UTC),
        "America/La_Paz",
    )
    local = ZoneInfo("America/La_Paz")
    assert start.astimezone(local).isoformat() == "2026-12-01T00:00:00-04:00"
    assert end.astimezone(local).isoformat() == "2027-01-01T00:00:00-04:00"


@pytest.mark.parametrize(
    ("hours_before", "timely", "restore_quota", "blocks_booking"),
    [
        (25, True, True, False),
        (24, True, True, False),
        (23, False, False, True),
        (0, False, False, True),
    ],
)
def test_cancellation_policy_uses_the_ratified_24_hour_boundary(
    hours_before: int,
    timely: bool,
    restore_quota: bool,
    blocks_booking: bool,
):
    from app.services.exchange_session_policy import classify_cancellation

    starts_at = datetime(2026, 11, 20, 18, tzinfo=UTC)
    result = classify_cancellation(
        starts_at=starts_at,
        cancelled_at=starts_at - timedelta(hours=hours_before),
        actor_monthly_cancellations=0,
    )
    assert result.is_timely is timely
    assert result.restore_quota is restore_quota
    assert result.blocks_booking is blocks_booking


@pytest.mark.parametrize(
    ("previous_count", "blocks_booking"),
    [(0, False), (2, False), (3, True), (4, True)],
)
def test_fourth_monthly_cancellation_starts_the_booking_block(
    previous_count: int,
    blocks_booking: bool,
):
    from app.services.exchange_session_policy import classify_cancellation

    starts_at = datetime(2026, 11, 30, 18, tzinfo=UTC)
    result = classify_cancellation(
        starts_at=starts_at,
        cancelled_at=starts_at - timedelta(days=2),
        actor_monthly_cancellations=previous_count,
    )
    assert result.blocks_booking is blocks_booking
    if blocks_booking:
        assert result.booking_blocked_until == result.cancelled_at + timedelta(days=7)
    else:
        assert result.booking_blocked_until is None


def test_paid_flow_is_not_reported_available_without_hu42():
    from app.services.exchange_session_policy import FreeQuotaDecision, decide_quota

    decision = decide_quota(free_sessions_used=2, payment_gateway_available=False)
    assert decision is FreeQuotaDecision.PAYMENT_REQUIRED_UNAVAILABLE
