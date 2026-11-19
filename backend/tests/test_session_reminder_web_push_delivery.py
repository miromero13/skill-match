"""PostgreSQL contracts for auditable HU-38 Web Push reminder delivery."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import select, update

from app.db.session import AsyncSessionLocal
from app.main import create_application
from app.models.notification_preference import NotificationPreference
from app.models.web_push_subscription import WebPushSubscription
from tests.test_exchange_sessions_db_behavior import (
    assert_envelope,
    create_payload,
    headers,
    seeded_exchange,
)


async def _accepted_session(seed: dict, starts_at: datetime) -> dict:
    app = create_application()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test",
    ) as client:
        created = assert_envelope(
            await client.post(
                "/api/sessions",
                headers=headers(seed["learner"]),
                json=create_payload(seed, starts_at=starts_at),
            ),
            201,
        )["data"]
        assert_envelope(
            await client.patch(
                f"/api/sessions/{created['id']}/status",
                headers=headers(seed["instructor"]),
                json={"status": "ACCEPTED"},
            ),
            200,
        )
    return created


def _subscription(user_id: UUID, suffix: str) -> WebPushSubscription:
    endpoint = f"https://push.example.test/send/{suffix}-{uuid4().hex}"
    from app.services.web_push_subscription_service import WebPushSubscriptionService

    return WebPushSubscription(
        user_id=user_id,
        endpoint=endpoint,
        endpoint_hash=WebPushSubscriptionService.endpoint_hash(endpoint),
        p256dh=f"p256dh-{suffix}",
        auth=f"auth-{suffix}",
        device_label=f"Device {suffix}",
        is_active=True,
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_push_delivery_is_once_per_event_and_active_device() -> None:
    from app.models.exchange_session import SessionReminderWebPushDelivery
    from app.services.session_reminder_service import dispatch_due_reminders
    from app.services.session_reminder_web_push_delivery_service import (
        deliver_pending_reminder_web_push,
    )

    class AcceptedSender:
        def __init__(self) -> None:
            self.deliveries: list[tuple[str, str]] = []

        async def send(self, subscription, payload) -> int:
            self.deliveries.append((subscription.endpoint, payload.to_json()))
            return 201

    async with seeded_exchange() as seed:
        starts_at = datetime.now(UTC) + timedelta(days=3)
        created = await _accepted_session(seed, starts_at)
        async with AsyncSessionLocal() as db:
            db.add_all([
                NotificationPreference(user_id=seed["instructor"].id, push=True),
                NotificationPreference(user_id=seed["learner"].id, push=True),
                _subscription(seed["instructor"].id, "instructor-one"),
                _subscription(seed["instructor"].id, "instructor-two"),
                _subscription(seed["learner"].id, "learner-one"),
            ])
            await db.commit()

        reminder_now = starts_at - timedelta(hours=24)
        async with AsyncSessionLocal() as db:
            await dispatch_due_reminders(db, now=reminder_now)
            await db.commit()
            pending = list((await db.scalars(select(SessionReminderWebPushDelivery).where(
                SessionReminderWebPushDelivery.session_id == UUID(created["id"]),
            ))).all())
        assert len(pending) == 3
        assert len({item.delivery_id for item in pending}) == 3

        sender = AcceptedSender()
        async with AsyncSessionLocal() as db:
            first = await deliver_pending_reminder_web_push(db, sender=sender, now=reminder_now)
            await db.commit()
        async with AsyncSessionLocal() as db:
            replay = await deliver_pending_reminder_web_push(db, sender=sender, now=reminder_now)
            await db.commit()
            stored = list((await db.scalars(select(SessionReminderWebPushDelivery).where(
                SessionReminderWebPushDelivery.session_id == UUID(created["id"]),
            ))).all())
        assert first.sent == 3
        assert replay.sent == 0
        assert len(sender.deliveries) == 3
        assert {item.status for item in stored} == {"SENT"}
        assert {item.attempt_count for item in stored} == {1}


@pytest.mark.asyncio(loop_scope="session")
async def test_expired_device_is_disabled_and_transient_failure_is_bounded() -> None:
    from app.models.exchange_session import SessionReminderWebPushDelivery
    from app.services.session_reminder_service import dispatch_due_reminders
    from app.services.session_reminder_web_push_delivery_service import (
        deliver_pending_reminder_web_push,
    )

    class StatusSender:
        async def send(self, subscription, payload) -> int:
            del payload
            return 410 if "expired" in subscription.device_label else 503

    async with seeded_exchange() as seed:
        starts_at = datetime.now(UTC) + timedelta(days=3)
        created = await _accepted_session(seed, starts_at)
        async with AsyncSessionLocal() as db:
            db.add(NotificationPreference(user_id=seed["learner"].id, push=True))
            db.add_all([
                _subscription(seed["learner"].id, "expired"),
                _subscription(seed["learner"].id, "transient"),
            ])
            await db.commit()
        reminder_now = starts_at - timedelta(hours=24)
        async with AsyncSessionLocal() as db:
            await dispatch_due_reminders(db, now=reminder_now)
            await db.commit()
        sender = StatusSender()
        for _ in range(3):
            async with AsyncSessionLocal() as db:
                await deliver_pending_reminder_web_push(db, sender=sender, now=reminder_now)
                await db.commit()
        async with AsyncSessionLocal() as db:
            deliveries = list((await db.scalars(select(SessionReminderWebPushDelivery).where(
                SessionReminderWebPushDelivery.session_id == UUID(created["id"]),
            ))).all())
            subscriptions = list((await db.scalars(select(WebPushSubscription).where(
                WebPushSubscription.user_id == seed["learner"].id,
            ))).all())
        by_label = {item.device_label: item for item in subscriptions}
        assert by_label["Device expired"].is_active is False
        assert by_label["Device transient"].is_active is True
        assert {item.status for item in deliveries} == {"SKIPPED", "FAILED"}
        assert {item.attempt_count for item in deliveries} == {1, 3}


@pytest.mark.asyncio(loop_scope="session")
async def test_push_rechecks_preference_before_network_send() -> None:
    from app.models.exchange_session import SessionReminderWebPushDelivery
    from app.services.session_reminder_service import dispatch_due_reminders
    from app.services.session_reminder_web_push_delivery_service import (
        deliver_pending_reminder_web_push,
    )

    class RejectUnexpectedSend:
        async def send(self, subscription, payload) -> int:
            raise AssertionError(f"Unexpected push to {subscription.id}: {payload.event_id}")

    async with seeded_exchange() as seed:
        starts_at = datetime.now(UTC) + timedelta(days=3)
        created = await _accepted_session(seed, starts_at)
        async with AsyncSessionLocal() as db:
            preference = NotificationPreference(user_id=seed["learner"].id, push=True)
            db.add_all([preference, _subscription(seed["learner"].id, "disabled")])
            await db.commit()
        reminder_now = starts_at - timedelta(hours=24)
        async with AsyncSessionLocal() as db:
            await dispatch_due_reminders(db, now=reminder_now)
            await db.execute(update(NotificationPreference).where(
                NotificationPreference.user_id == seed["learner"].id,
            ).values(push=False))
            await db.commit()
        async with AsyncSessionLocal() as db:
            result = await deliver_pending_reminder_web_push(
                db, sender=RejectUnexpectedSend(), now=reminder_now,
            )
            await db.commit()
            delivery = await db.scalar(select(SessionReminderWebPushDelivery).where(
                SessionReminderWebPushDelivery.session_id == UUID(created["id"]),
            ))
        assert result.skipped == 1
        assert delivery is not None
        assert delivery.status == "SKIPPED"
        assert delivery.skipped_reason == "PREFERENCE_DISABLED"
