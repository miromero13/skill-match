"""Pure domain policies for session completion, presence PINs, and no-show eligibility.

Contains deterministic, side-effect-free functions implementing:
- 4-digit PIN generation, constant-time hashing and verification.
- Session confirmation eligibility and dual-matching evaluation.
- No-show reporting window and conflict guards.
"""

import hashlib
import hmac
import secrets
from datetime import datetime
from uuid import UUID


def generate_presence_pin(*, session_id: UUID, user_id: UUID, secret: str) -> str:
    """Derive a stable, server-secret 4-digit PIN for one session participant."""
    subject = f"session-presence:{session_id}:{user_id}".encode()
    digest = hmac.new(secret.encode(), subject, hashlib.sha256).digest()
    return f"{int.from_bytes(digest[:8], 'big') % 10000:04d}"


def hash_presence_pin(pin: str, *, session_id: UUID, user_id: UUID, secret: str) -> str:
    """Authenticate a PIN with a server-side pepper and record context."""
    subject = f"session-presence-hash:{session_id}:{user_id}:{pin}".encode()
    return hmac.new(secret.encode(), subject, hashlib.sha256).hexdigest()


def verify_presence_pin(
    *,
    stored_hash: str,
    candidate_pin: str,
    session_id: UUID,
    user_id: UUID,
    secret: str,
    attempt_count: int,
    locked_at: datetime | None,
    expires_at: datetime,
    now: datetime,
) -> tuple[bool, bool, str | None]:
    """Verify presence PIN against attempts, expiration and constant-time digest.

    Returns:
        (is_valid, is_locked, error_code)
    """
    if locked_at is not None or attempt_count >= 5:
        return False, True, "PIN_LOCKED"

    if now > expires_at:
        return False, False, "PIN_EXPIRED"

    candidate_hash = hash_presence_pin(
        candidate_pin,
        session_id=session_id,
        user_id=user_id,
        secret=secret,
    )
    if secrets.compare_digest(stored_hash, candidate_hash):
        return True, False, None

    return False, False, "PIN_INVALID"


def evaluate_confirmation_transition(
    *,
    session_status: str,
    ends_at: datetime,
    existing_confirmation: dict | None,
    new_minutes: int,
    now: datetime,
) -> tuple[bool, str]:
    """Evaluate whether confirmation can proceed and if it completes the session.

    Returns:
        (can_proceed, outcome_reason)
    """
    if session_status != "ACCEPTED":
        return False, "INVALID_STATUS"

    if now < ends_at:
        return False, "SESSION_NOT_ENDED"

    if existing_confirmation is None:
        return True, "FIRST_CONFIRMATION"

    if existing_confirmation.get("actual_minutes") != new_minutes:
        return False, "MINUTES_MISMATCH"

    return True, "COMPLETED"


def evaluate_noshow_eligibility(
    *,
    session_status: str,
    ends_at: datetime,
    counterpart_confirmed: bool,
    now: datetime,
) -> tuple[bool, str]:
    """Evaluate whether an actor can report a no-show incident.

    Returns:
        (is_eligible, outcome_reason)
    """
    if session_status != "ACCEPTED":
        return False, "INVALID_STATUS"

    if now < ends_at:
        return False, "SESSION_NOT_ENDED"

    if counterpart_confirmed:
        return False, "COUNTERPART_ALREADY_CONFIRMED"

    return True, "ELIGIBLE"
