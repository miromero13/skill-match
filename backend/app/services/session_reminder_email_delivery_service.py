"""Durable, duplicate-resistant SMTP delivery for HU-38 reminders."""

import smtplib
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.catalog import Skill
from app.models.exchange_session import (
    ExchangeSession,
    SessionReminderDispatch,
    SessionReminderEmailDelivery,
)
from app.models.teaching_skill import TeachingSkill
from app.models.user import User
from app.services.email_service import SMTPFailureKind, classify_smtp_failure
from app.services.notification_service import NotificationService
from app.services.session_email_service import (
    ReminderEmailContent,
    build_session_reminder_email,
)


class ReminderEmailSender(Protocol):
    async def send(self, content: ReminderEmailContent) -> None: ...


@dataclass(frozen=True, slots=True)
class EmailDeliveryResult:
    sent: int = 0
    failed: int = 0
    skipped: int = 0


async def deliver_pending_reminder_emails(
    db: AsyncSession,
    *,
    sender: ReminderEmailSender,
    now: datetime,
    sessions_url: str,
    batch_size: int = 50,
) -> EmailDeliveryResult:
    """Claim pending rows and record outcomes; caller owns the transaction.

    The row lock prevents ordinary concurrent duplicates. SMTP cannot guarantee
    exactly-once if the process dies after provider acceptance and before commit;
    the stable Message-ID makes that ambiguity observable and duplicate-resistant.
    """
    counterpart = aliased(User)
    recipient = aliased(User)
    counterpart_id = case(
        (
            ExchangeSession.instructor_id == SessionReminderEmailDelivery.user_id,
            ExchangeSession.learner_id,
        ),
        else_=ExchangeSession.instructor_id,
    )
    rows = (
        await db.execute(
            select(
                SessionReminderEmailDelivery,
                SessionReminderDispatch,
                ExchangeSession,
                recipient,
                counterpart,
                Skill.name,
            )
            .join(
                SessionReminderDispatch,
                SessionReminderDispatch.id == SessionReminderEmailDelivery.dispatch_id,
            )
            .join(
                ExchangeSession,
                ExchangeSession.id == SessionReminderEmailDelivery.session_id,
            )
            .join(recipient, recipient.id == SessionReminderEmailDelivery.user_id)
            .join(TeachingSkill, TeachingSkill.id == ExchangeSession.teaching_skill_id)
            .join(Skill, Skill.id == TeachingSkill.skill_id)
            .join(counterpart, counterpart.id == counterpart_id)
            .where(
                SessionReminderEmailDelivery.status == "PENDING",
                SessionReminderEmailDelivery.attempt_count < 3,
            )
            .order_by(SessionReminderEmailDelivery.created_at, SessionReminderEmailDelivery.id)
            .limit(batch_size)
            .with_for_update(skip_locked=True, of=SessionReminderEmailDelivery)
        )
    ).all()

    sent = failed = skipped = 0
    for delivery, dispatch, session, user, other_user, skill_name in rows:
        if session.status != "ACCEPTED":
            delivery.status = "SKIPPED"
            delivery.skipped_reason = "SESSION_NOT_ACCEPTED"
            skipped += 1
            continue
        if session.starts_at != dispatch.session_starts_at:
            delivery.status = "SKIPPED"
            delivery.skipped_reason = "SESSION_RESCHEDULED"
            skipped += 1
            continue
        if session.starts_at <= now:
            delivery.status = "SKIPPED"
            delivery.skipped_reason = "SESSION_STARTED"
            skipped += 1
            continue
        channels = await NotificationService.resolve_channels(
            db,
            user.id,
            "SESSION_REMINDER",
        )
        if not channels.email:
            delivery.status = "SKIPPED"
            delivery.skipped_reason = "PREFERENCE_DISABLED"
            skipped += 1
            continue

        content = build_session_reminder_email(
            event_id=delivery.event_id,
            threshold=dispatch.threshold,
            recipient_name=user.full_name,
            recipient_email=user.email,
            counterpart_name=other_user.full_name,
            skill_name=skill_name,
            starts_at=session.starts_at,
            timezone=session.timezone,
            modality=session.modality,
            sessions_url=sessions_url,
        )
        delivery.attempt_count += 1
        try:
            await sender.send(content)
        except (smtplib.SMTPException, OSError) as exc:
            failure = classify_smtp_failure(exc)
            delivery.last_error_kind = failure.value
            if failure is not SMTPFailureKind.TRANSIENT or delivery.attempt_count >= 3:
                delivery.status = "FAILED"
            failed += 1
            continue

        delivery.status = "SENT"
        delivery.sent_at = now
        delivery.last_error_kind = None
        sent += 1

    return EmailDeliveryResult(sent=sent, failed=failed, skipped=skipped)
