"""Auditable and idempotent Web Push delivery for HU-38 reminders."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.exchange_session import (
    ExchangeSession,
    SessionReminderDispatch,
    SessionReminderWebPushDelivery,
)
from app.models.web_push_subscription import WebPushSubscription
from app.services.notification_service import NotificationService
from app.services.session_web_push_service import (
    SessionReminderPushPayload,
    WebPushFailureKind,
    build_session_reminder_push,
    resolve_web_push_outcome,
)


class ReminderWebPushSender(Protocol):
    async def send(
        self, subscription: WebPushSubscription, payload: SessionReminderPushPayload,
    ) -> int: ...


@dataclass(frozen=True, slots=True)
class WebPushDeliveryResult:
    sent: int = 0
    failed: int = 0
    skipped: int = 0


async def deliver_pending_reminder_web_push(
    db: AsyncSession,
    *,
    sender: ReminderWebPushSender,
    now: datetime,
    batch_size: int = 100,
) -> WebPushDeliveryResult:
    rows = (await db.execute(
        select(
            SessionReminderWebPushDelivery,
            SessionReminderDispatch,
            ExchangeSession,
            WebPushSubscription,
        )
        .join(SessionReminderDispatch, SessionReminderDispatch.id == SessionReminderWebPushDelivery.dispatch_id)
        .join(ExchangeSession, ExchangeSession.id == SessionReminderWebPushDelivery.session_id)
        .join(WebPushSubscription, WebPushSubscription.id == SessionReminderWebPushDelivery.subscription_id)
        .where(
            SessionReminderWebPushDelivery.status == "PENDING",
            SessionReminderWebPushDelivery.attempt_count < 3,
        )
        .order_by(SessionReminderWebPushDelivery.created_at, SessionReminderWebPushDelivery.id)
        .limit(batch_size)
        .with_for_update(skip_locked=True, of=SessionReminderWebPushDelivery)
    )).all()
    sent = failed = skipped = 0
    for delivery, dispatch, session, subscription in rows:
        reason = None
        if session.status != "ACCEPTED":
            reason = "SESSION_NOT_ACCEPTED"
        elif session.starts_at != dispatch.session_starts_at:
            reason = "SESSION_RESCHEDULED"
        elif session.starts_at <= now:
            reason = "SESSION_STARTED"
        elif not subscription.is_active:
            reason = "SUBSCRIPTION_INACTIVE"
        else:
            channels = await NotificationService.resolve_channels(
                db, delivery.user_id, "SESSION_REMINDER",
            )
            if not channels.push:
                reason = "PREFERENCE_DISABLED"
        if reason:
            delivery.status = "SKIPPED"
            delivery.skipped_reason = reason
            skipped += 1
            continue

        payload = build_session_reminder_push(
            event_id=delivery.event_id, threshold=dispatch.threshold,
        )
        delivery.attempt_count += 1
        try:
            status_code = await sender.send(subscription, payload)
        except OSError:
            status_code = 503
        outcome = resolve_web_push_outcome(
            status_code=status_code, attempt_count=delivery.attempt_count,
        )
        delivery.last_status_code = status_code
        delivery.last_error_kind = (
            None if outcome.failure_kind is WebPushFailureKind.SUCCESS
            else outcome.failure_kind.value
        )
        delivery.status = outcome.delivery_status
        if not outcome.subscription_active:
            subscription.is_active = False
            subscription.revoked_at = now
            delivery.skipped_reason = "SUBSCRIPTION_EXPIRED"
        if outcome.delivery_status == "SENT":
            delivery.sent_at = now
            sent += 1
        elif outcome.delivery_status == "SKIPPED":
            skipped += 1
        else:
            failed += 1
    return WebPushDeliveryResult(sent=sent, failed=failed, skipped=skipped)
