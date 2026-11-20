"""Behavior contracts for HU-38 integrations with HU-39, HU-40 and HU-42.

These tests intentionally describe the cross-story contract before production
services are changed.  They must fail only where the integration boundary is
still missing; existing free-session behavior remains covered by HU-38 suites.
"""

import inspect
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest


def _create_payload(**overrides: object) -> dict[str, object]:
    starts_at = datetime.now(UTC) + timedelta(days=3)
    payload: dict[str, object] = {
        "match_id": uuid4(),
        "teaching_skill_id": uuid4(),
        "instructor_id": uuid4(),
        "starts_at": starts_at,
        "ends_at": starts_at + timedelta(minutes=60),
        "timezone": "America/La_Paz",
        "modality": "VIRTUAL",
    }
    payload.update(overrides)
    return payload


def test_paid_creation_requires_explicit_points_consent() -> None:
    """A member must opt in before POST /sessions can reserve real points."""
    from app.schemas.exchange_session import ExchangeSessionCreate

    request = ExchangeSessionCreate(**_create_payload(payment_method="POINTS"))

    assert request.payment_method == "POINTS"


def test_free_creation_preserves_backward_compatible_default() -> None:
    """Existing clients keep requesting a free quota unless they opt in."""
    from app.schemas.exchange_session import ExchangeSessionCreate

    request = ExchangeSessionCreate(**_create_payload())

    assert request.payment_method == "FREE"


def test_session_response_exposes_canonical_payment_state() -> None:
    """Frontend must receive backend-owned price and persisted escrow state."""
    from app.schemas.exchange_session import ExchangeSessionResponse

    starts_at = datetime.now(UTC) + timedelta(days=3)
    response = ExchangeSessionResponse(
        id=uuid4(),
        match_id=uuid4(),
        teaching_skill_id=uuid4(),
        created_by_id=uuid4(),
        instructor_id=uuid4(),
        learner_id=uuid4(),
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=60),
        timezone="America/La_Paz",
        modality="VIRTUAL",
        status="PENDING",
        is_free=False,
        points_required=50,
        payment_state="RESERVED",
        quota_restored=False,
    )

    assert response.points_required == 50
    assert response.payment_state == "RESERVED"


@pytest.mark.asyncio
async def test_completion_replay_never_assumes_escrow_release_without_db() -> None:
    """An idempotent replay may not claim a financial side effect it did not verify."""
    from app.services.session_escrow_adapter import SessionEscrowAdapter

    result = await SessionEscrowAdapter.process_completion(
        session_id=str(uuid4()),
        is_free=False,
        points_required=50,
        db=None,
    )

    assert result == "PENDING_HU42"


def test_wallet_contract_includes_idempotent_session_refund() -> None:
    """Rejection/cancellation/reschedule need a canonical HU-42 compensation."""
    from app.services.wallet_service import wallet_service

    assert hasattr(wallet_service, "refund_session_escrow")


@pytest.mark.asyncio
async def test_noshow_boundary_accepts_transaction_and_finishes_processing() -> None:
    """HU-39 incidents must be processed through HU-40 in the same unit of work."""
    from app.services.session_reputation_adapter import SessionReputationAdapter

    class FakeSession:
        pass

    result = await SessionReputationAdapter.record_noshow_incident(
        db=FakeSession(),
        session_id=uuid4(),
        absent_user_id=uuid4(),
        reported_by_id=uuid4(),
    )

    assert result == "PROCESSED"


def test_passport_remains_a_downstream_reputation_consumer() -> None:
    """HU-41 must not become a dependency of the HU-38 creation service."""
    from app.services import exchange_session_service

    source = inspect.getsource(exchange_session_service)
    assert "passport" not in source.lower()
