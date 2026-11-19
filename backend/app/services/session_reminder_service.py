from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.exchange_session import (
    ExchangeSession,
    SessionReminderDispatch,
    SessionReminderEmailDelivery,
    SessionReminderWebPushDelivery,
)
from app.models.notification import NotificationType
from app.models.web_push_subscription import WebPushSubscription
from app.services.notification_service import NotificationService
from app.services.session_email_service import reminder_email_message_id
from app.services.session_reminder_policy import (
    ReminderThreshold,
    due_reminder_thresholds,
    is_reminder_eligible,
    reminder_event_id,
)
from app.services.session_web_push_service import web_push_delivery_identity


@dataclass(frozen=True, slots=True)
class ReminderEmission:
    user_id: UUID
    event_id: UUID
    notification_type: NotificationType
    title: str
    message: str


def build_reminder_emissions(
    *,
    session_id: UUID,
    instructor_id: UUID,
    learner_id: UUID,
    starts_at: datetime,
    threshold: ReminderThreshold,
) -> tuple[ReminderEmission, ReminderEmission]:
    """Build stable domain emissions for both participants without performing I/O."""
    label = "24 horas" if threshold == "24H" else "1 hora"
    def emission_for(user_id: UUID) -> ReminderEmission:
        return ReminderEmission(
            user_id=user_id,
            event_id=reminder_event_id(session_id, user_id, threshold, starts_at),
            notification_type=NotificationType.SESSION_REMINDER,
            title="Recordatorio de sesión",
            message=f"Tu sesión de intercambio comienza en {label}.",
        )

    return emission_for(instructor_id), emission_for(learner_id)


async def dispatch_due_reminders(
    db: AsyncSession,
    *,
    now: datetime,
    lookback: timedelta = timedelta(minutes=5),
) -> list[UUID]:
    """Persist each due dispatch once and return newly created notification IDs."""
    candidates = list(
        (
            await db.scalars(
                select(ExchangeSession).where(
                    ExchangeSession.status == "ACCEPTED",
                    ExchangeSession.starts_at > now,
                    ExchangeSession.starts_at > now + timedelta(hours=1) - lookback,
                    ExchangeSession.starts_at <= now + timedelta(hours=24),
                )
            )
        ).all()
    )
    notification_ids: list[UUID] = []
    for session in candidates:
        if not is_reminder_eligible(session.status, session.starts_at, now):
            continue
        for threshold in due_reminder_thresholds(
            session.starts_at,
            now,
            lookback=lookback,
        ):
            emissions = build_reminder_emissions(
                session_id=session.id,
                instructor_id=session.instructor_id,
                learner_id=session.learner_id,
                starts_at=session.starts_at,
                threshold=threshold,
            )
            for emission in emissions:
                dispatch_id = await db.scalar(
                    insert(SessionReminderDispatch)
                    .values(
                        id=uuid4(),
                        session_id=session.id,
                        user_id=emission.user_id,
                        threshold=threshold,
                        session_starts_at=session.starts_at,
                        event_id=emission.event_id,
                    )
                    .on_conflict_do_nothing(
                        constraint="uq_session_reminder_dispatch_identity",
                    )
                    .returning(SessionReminderDispatch.id)
                )
                if dispatch_id is None:
                    continue
                channels = await NotificationService.resolve_channels(
                    db,
                    emission.user_id,
                    emission.notification_type,
                )
                if channels.email:
                    await db.execute(
                        insert(SessionReminderEmailDelivery)
                        .values(
                            id=uuid4(),
                            dispatch_id=dispatch_id,
                            session_id=session.id,
                            user_id=emission.user_id,
                            event_id=emission.event_id,
                            message_id=reminder_email_message_id(emission.event_id),
                            status="PENDING",
                            attempt_count=0,
                        )
                        .on_conflict_do_nothing(
                            constraint="uq_session_reminder_email_dispatch",
                        )
                    )
                if channels.push:
                    subscriptions = list((await db.scalars(
                        select(WebPushSubscription).where(
                            WebPushSubscription.user_id == emission.user_id,
                            WebPushSubscription.is_active.is_(True),
                        )
                    )).all())
                    for subscription in subscriptions:
                        await db.execute(
                            insert(SessionReminderWebPushDelivery)
                            .values(
                                id=uuid4(),
                                dispatch_id=dispatch_id,
                                subscription_id=subscription.id,
                                session_id=session.id,
                                user_id=emission.user_id,
                                event_id=emission.event_id,
                                delivery_id=web_push_delivery_identity(
                                    emission.event_id, subscription.id,
                                ),
                                status="PENDING",
                                attempt_count=0,
                            )
                            .on_conflict_do_nothing(
                                constraint="uq_session_reminder_web_push_event_subscription",
                            )
                        )
                notification = await NotificationService.emit_in_app(
                    db,
                    user_id=emission.user_id,
                    event_id=emission.event_id,
                    notification_type=emission.notification_type,
                    title=emission.title,
                    message=emission.message,
                )
                if notification is not None:
                    await db.execute(
                        update(SessionReminderDispatch)
                        .where(SessionReminderDispatch.id == dispatch_id)
                        .values(notification_id=notification.id)
                    )
                    notification_ids.append(notification.id)
    return notification_ids
