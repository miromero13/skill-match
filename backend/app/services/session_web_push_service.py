"""Pure HU-38 Web Push policy; no database, VAPID or network I/O."""

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum
from uuid import NAMESPACE_URL, UUID, uuid5

from app.services.session_reminder_policy import ReminderThreshold


class WebPushFailureKind(StrEnum):
    SUCCESS = "SUCCESS"
    EXPIRED = "EXPIRED"
    TRANSIENT = "TRANSIENT"
    PERMANENT = "PERMANENT"
    CONFIGURATION = "CONFIGURATION"


@dataclass(frozen=True, slots=True)
class SessionReminderPushPayload:
    type: str
    title: str
    body: str
    url: str
    event_id: UUID

    def to_json(self) -> str:
        return json.dumps(asdict(self), default=str, ensure_ascii=False, separators=(",", ":"))


@dataclass(frozen=True, slots=True)
class WebPushOutcome:
    delivery_status: str
    subscription_active: bool
    retry: bool
    failure_kind: WebPushFailureKind


def build_session_reminder_push(
    *,
    event_id: UUID,
    threshold: ReminderThreshold,
) -> SessionReminderPushPayload:
    if threshold not in {"24H", "1H"}:
        raise ValueError("Umbral de recordatorio no soportado")
    label = "24 horas" if threshold == "24H" else "1 hora"
    return SessionReminderPushPayload(
        type="SESSION_REMINDER",
        title="Recordatorio de sesión",
        body=f"Tu sesión de intercambio comienza en {label}.",
        url="/app/sessions",
        event_id=event_id,
    )


def web_push_delivery_identity(event_id: UUID, subscription_id: UUID) -> UUID:
    """Stable per event/device, allowing one user to own several subscriptions."""
    return uuid5(
        NAMESPACE_URL,
        f"skillmatch:web-push-delivery:{event_id}:{subscription_id}",
    )


def classify_web_push_status(status_code: int) -> WebPushFailureKind:
    if 200 <= status_code < 300:
        return WebPushFailureKind.SUCCESS
    if status_code in {404, 410}:
        return WebPushFailureKind.EXPIRED
    if status_code in {401, 403}:
        return WebPushFailureKind.CONFIGURATION
    if status_code == 429 or 500 <= status_code < 600:
        return WebPushFailureKind.TRANSIENT
    return WebPushFailureKind.PERMANENT


def resolve_web_push_outcome(*, status_code: int, attempt_count: int) -> WebPushOutcome:
    if not 1 <= attempt_count <= 3:
        raise ValueError("attempt_count debe estar entre 1 y 3")
    kind = classify_web_push_status(status_code)
    if kind is WebPushFailureKind.SUCCESS:
        return WebPushOutcome("SENT", True, False, kind)
    if kind is WebPushFailureKind.EXPIRED:
        return WebPushOutcome("SKIPPED", False, False, kind)
    if kind is WebPushFailureKind.TRANSIENT and attempt_count < 3:
        return WebPushOutcome("PENDING", True, True, kind)
    return WebPushOutcome("FAILED", True, False, kind)


def is_web_push_delivery_eligible(
    *,
    preference_enabled: bool,
    subscription_active: bool,
    session_status: str,
    expected_starts_at: datetime,
    current_starts_at: datetime,
    now: datetime,
) -> bool:
    return (
        preference_enabled
        and subscription_active
        and session_status == "ACCEPTED"
        and expected_starts_at == current_starts_at
        and current_starts_at > now
    )
