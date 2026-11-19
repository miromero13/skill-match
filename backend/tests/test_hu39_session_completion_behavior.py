"""HU-39 behavioral contract and policy specifications (TDD - Red Phase).

Validates the contracts, policies, and API requirements for:
- Dual confirmation of completed sessions (RF-SES-07)
- In-person presence PIN generation and verification
- Auditable no-show incident reporting (RF-SES-12)
- Absence of fictional escrow movements (HU-42 boundary) or reputation penalties (HU-40 boundary).
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError


def test_hu39_routes_are_registered_in_openapi():
    """Verify that OpenAPI schema defines the required HU-39 endpoints."""
    from app.main import create_application

    paths = create_application().openapi()["paths"]
    expected = {
        "/api/sessions/{session_id}/confirm": {"post"},
        "/api/sessions/{session_id}/report-noshow": {"post"},
    }
    for path, methods in expected.items():
        assert path in paths, f"Route {path} must be registered in OpenAPI"
        assert methods <= set(paths[path]), f"Methods {methods} must be registered for {path}"


def test_confirm_request_schema_validation():
    """Test SessionConfirmRequest schema rules."""
    from app.schemas.exchange_session import SessionConfirmRequest

    key = uuid4()
    # Valid payload
    payload = SessionConfirmRequest(
        request_key=key,
        actual_minutes=60,
        topics=["FastAPI async", "PostgreSQL transactions"],
        presence_pin="7492",
    )
    assert payload.request_key == key
    assert payload.actual_minutes == 60
    assert len(payload.topics) == 2
    assert payload.presence_pin == "7492"

    # Reject duration outside 1..60
    for invalid_minutes in [0, -1, 61, 120]:
        with pytest.raises(ValidationError):
            SessionConfirmRequest(
                request_key=key,
                actual_minutes=invalid_minutes,
                topics=[],
            )

    # Reject invalid presence pin format (must be 4 digits)
    for invalid_pin in ["12", "123", "12345", "abcd", " 123", "123 "]:
        with pytest.raises(ValidationError):
            SessionConfirmRequest(
                request_key=key,
                actual_minutes=45,
                topics=[],
                presence_pin=invalid_pin,
            )

    # Reject more than 10 topics
    with pytest.raises(ValidationError):
        SessionConfirmRequest(
            request_key=key,
            actual_minutes=60,
            topics=[f"Topic {i}" for i in range(11)],
        )


def test_confirm_response_schema_structure():
    """Test SessionConfirmResponse schema contract."""
    from app.schemas.exchange_session import SessionConfirmResponse

    session_id = uuid4()
    resp = SessionConfirmResponse(
        session_id=session_id,
        status="ACCEPTED",
        my_confirmation=True,
        counterpart_confirmation=False,
        actual_minutes=60,
        completed_at=None,
        escrow_release="NOT_APPLICABLE",
    )
    assert resp.session_id == session_id
    assert resp.status == "ACCEPTED"
    assert resp.my_confirmation is True
    assert resp.counterpart_confirmation is False
    assert resp.actual_minutes == 60
    assert resp.completed_at is None
    assert resp.escrow_release == "NOT_APPLICABLE"


def test_noshow_request_schema_validation():
    """Test SessionNoShowRequest schema rules."""
    from app.schemas.exchange_session import SessionNoShowRequest

    key = uuid4()
    # Valid reason
    valid = SessionNoShowRequest(
        request_key=key,
        reason="La contraparte no se conecto ni respondio los mensajes.",
    )
    assert valid.request_key == key
    assert "no se conecto" in valid.reason

    # Reject reason < 10 characters or > 500 characters
    for invalid_reason in ["", "   ", "corto", "a" * 9, "b" * 501]:
        with pytest.raises(ValidationError):
            SessionNoShowRequest(
                request_key=key,
                reason=invalid_reason,
            )


def test_noshow_response_schema_structure():
    """Test SessionNoShowResponse schema contract."""
    from app.schemas.exchange_session import SessionNoShowResponse

    session_id = uuid4()
    reported_by = uuid4()
    absent_user = uuid4()
    now = datetime.now(UTC)

    resp = SessionNoShowResponse(
        session_id=session_id,
        reported_by_id=reported_by,
        absent_user_id=absent_user,
        reason="Inasistencia injustificada sin previo aviso.",
        status="PENDING_REPUTATION",
        reported_at=now,
    )
    assert resp.session_id == session_id
    assert resp.status == "PENDING_REPUTATION"
    assert resp.absent_user_id == absent_user


def test_exchange_session_model_allows_completed_status():
    """Test that SessionStatus type in schemas admits COMPLETED."""
    from app.schemas.exchange_session import ExchangeSessionResponse

    session_id = uuid4()
    now = datetime.now(UTC)
    resp = ExchangeSessionResponse(
        id=session_id,
        match_id=uuid4(),
        teaching_skill_id=uuid4(),
        created_by_id=uuid4(),
        instructor_id=uuid4(),
        learner_id=uuid4(),
        starts_at=now,
        ends_at=now + timedelta(minutes=60),
        timezone="America/La_Paz",
        modality="VIRTUAL",
        status="COMPLETED",  # Must be allowed for HU-39
        is_free=True,
        quota_restored=False,
        actual_minutes=60,
        completed_at=now + timedelta(minutes=60),
    )
    assert resp.status == "COMPLETED"
    assert resp.actual_minutes == 60
    assert resp.completed_at is not None


def test_presence_pin_policy():
    """Test policy for generating, hashing and verifying 4-digit presence PINs."""
    from app.services.session_completion_policy import (
        generate_presence_pin,
        hash_presence_pin,
        verify_presence_pin,
    )

    session_id = uuid4()
    user_id = uuid4()
    secret = "hu39-test-secret"
    pin = generate_presence_pin(
        session_id=session_id,
        user_id=user_id,
        secret=secret,
    )
    assert len(pin) == 4
    assert pin.isdigit()

    pin_hash = hash_presence_pin(
        pin,
        session_id=session_id,
        user_id=user_id,
        secret=secret,
    )
    assert pin_hash != pin  # Never plaintext

    now = datetime.now(UTC)
    valid_until = now + timedelta(hours=24)

    # Correct PIN
    valid, is_locked, err = verify_presence_pin(
        stored_hash=pin_hash,
        candidate_pin=pin,
        session_id=session_id,
        user_id=user_id,
        secret=secret,
        attempt_count=0,
        locked_at=None,
        expires_at=valid_until,
        now=now,
    )
    assert valid is True
    assert is_locked is False
    assert err is None

    # Incorrect PIN
    valid, is_locked, err = verify_presence_pin(
        stored_hash=pin_hash,
        candidate_pin="0000" if pin != "0000" else "1111",
        session_id=session_id,
        user_id=user_id,
        secret=secret,
        attempt_count=1,
        locked_at=None,
        expires_at=valid_until,
        now=now,
    )
    assert valid is False
    assert is_locked is False
    assert err == "PIN_INVALID"

    # Locked PIN after 5 attempts
    valid, is_locked, err = verify_presence_pin(
        stored_hash=pin_hash,
        candidate_pin=pin,
        session_id=session_id,
        user_id=user_id,
        secret=secret,
        attempt_count=5,
        locked_at=now,
        expires_at=valid_until,
        now=now,
    )
    assert valid is False
    assert is_locked is True
    assert err == "PIN_LOCKED"

    # Expired PIN
    valid, is_locked, err = verify_presence_pin(
        stored_hash=pin_hash,
        candidate_pin=pin,
        session_id=session_id,
        user_id=user_id,
        secret=secret,
        attempt_count=0,
        locked_at=None,
        expires_at=now - timedelta(seconds=1),
        now=now,
    )
    assert valid is False
    assert err == "PIN_EXPIRED"


def test_session_completion_policy_timing_and_matching():
    """Test domain policy for completion timing and dual matching minutes."""
    from app.services.session_completion_policy import evaluate_confirmation_transition

    now = datetime(2026, 11, 20, 19, 0, tzinfo=UTC)
    ends_at = datetime(2026, 11, 20, 19, 0, tzinfo=UTC)

    # Before ends_at -> Cannot confirm
    can_confirm, reason = evaluate_confirmation_transition(
        session_status="ACCEPTED",
        ends_at=ends_at,
        existing_confirmation=None,
        new_minutes=60,
        now=now - timedelta(minutes=5),
    )
    assert can_confirm is False
    assert reason == "SESSION_NOT_ENDED"

    # Non-ACCEPTED session -> Cannot confirm
    for bad_status in ["PENDING", "REJECTED", "CANCELLED", "COMPLETED"]:
        can_confirm, reason = evaluate_confirmation_transition(
            session_status=bad_status,
            ends_at=ends_at,
            existing_confirmation=None,
            new_minutes=60,
            now=now,
        )
        assert can_confirm is False
        assert reason == "INVALID_STATUS"

    # First confirmation -> Recorded, does NOT complete
    can_confirm, reason = evaluate_confirmation_transition(
        session_status="ACCEPTED",
        ends_at=ends_at,
        existing_confirmation=None,
        new_minutes=60,
        now=now,
    )
    assert can_confirm is True
    assert reason == "FIRST_CONFIRMATION"

    # Second confirmation compatible -> Completes
    can_confirm, reason = evaluate_confirmation_transition(
        session_status="ACCEPTED",
        ends_at=ends_at,
        existing_confirmation={"actual_minutes": 60},
        new_minutes=60,
        now=now,
    )
    assert can_confirm is True
    assert reason == "COMPLETED"

    # Second confirmation mismatched -> Conflict
    can_confirm, reason = evaluate_confirmation_transition(
        session_status="ACCEPTED",
        ends_at=ends_at,
        existing_confirmation={"actual_minutes": 60},
        new_minutes=45,
        now=now,
    )
    assert can_confirm is False
    assert reason == "MINUTES_MISMATCH"
