from datetime import datetime, timedelta
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

ReminderThreshold = Literal["24H", "1H"]

_OFFSETS: dict[ReminderThreshold, timedelta] = {
    "24H": timedelta(hours=24),
    "1H": timedelta(hours=1),
}


def due_reminder_thresholds(
    starts_at: datetime,
    now: datetime,
    *,
    lookback: timedelta = timedelta(minutes=5),
) -> tuple[ReminderThreshold, ...]:
    """Return reminder thresholds whose target instant is in the active scan window."""
    if lookback <= timedelta(0):
        raise ValueError("La ventana de recordatorios debe ser positiva.")
    due: list[ReminderThreshold] = []
    for threshold, offset in _OFFSETS.items():
        target = starts_at - offset
        if target <= now < target + lookback:
            due.append(threshold)
    return tuple(due)


def is_reminder_eligible(status: str, starts_at: datetime, now: datetime) -> bool:
    return status == "ACCEPTED" and starts_at > now


def is_reminder_current(
    recorded_starts_at: datetime,
    current_starts_at: datetime,
    current_status: str,
) -> bool:
    return current_status == "ACCEPTED" and recorded_starts_at == current_starts_at


def reminder_event_id(
    session_id: UUID,
    recipient_id: UUID,
    threshold: ReminderThreshold,
    starts_at: datetime,
) -> UUID:
    """Build a deterministic event identity; rescheduling invalidates the old identity."""
    canonical_start = starts_at.isoformat()
    return uuid5(
        NAMESPACE_URL,
        f"skillmatch:session-reminder:{session_id}:{recipient_id}:{threshold}:{canonical_start}",
    )
