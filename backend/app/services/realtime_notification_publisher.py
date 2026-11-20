"""Post-commit bridge from the durable HU-25 inbox to HU-24 WebSockets."""
import asyncio
from collections import OrderedDict
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.session import AsyncSessionLocal
from app.models.notification import Notification
from app.schemas.notification import NotificationResponse
from app.schemas.realtime_notification import RealtimeNotificationEvent
from app.services.notification_connection_manager import (
    NotificationConnectionManager,
    notification_connection_manager,
)


class RealtimeNotificationPublisher:
    """Publish only rows visible from a fresh post-commit database session.

    Claims are process-local and intentionally at-most-once for the agreed
    single-worker deployment. A future multi-worker topology requires a shared
    bus/outbox and must replace this local claim registry.
    """

    def __init__(
        self,
        *,
        manager: NotificationConnectionManager,
        session_factory: async_sessionmaker[AsyncSession],
        max_claims: int = 10_000,
    ) -> None:
        if max_claims < 1:
            raise ValueError("max_claims debe ser positivo.")
        self._manager = manager
        self._session_factory = session_factory
        self._max_claims = max_claims
        self._claimed: OrderedDict[UUID, None] = OrderedDict()
        self._claim_lock = asyncio.Lock()

    async def _load_committed(self, notification_id: UUID) -> Notification | None:
        async with self._session_factory() as db:
            return await db.scalar(select(Notification).where(
                Notification.id == notification_id,
                Notification.deleted_at.is_(None),
            ))

    async def _claim(self, notification_id: UUID) -> bool:
        async with self._claim_lock:
            if notification_id in self._claimed:
                return False
            self._claimed[notification_id] = None
            while len(self._claimed) > self._max_claims:
                self._claimed.popitem(last=False)
            return True

    async def publish_committed(self, notification_id: UUID) -> int:
        """Publish a durable row once in this process, or return zero.

        Producers call this only after their transaction commits. The fresh
        session is an additional guard: an uncommitted/rolled-back row is not
        visible and therefore can never generate a WebSocket event.
        """
        item = await self._load_committed(notification_id)
        if item is None:
            return 0
        try:
            data = NotificationResponse.model_validate(item)
            event = RealtimeNotificationEvent(
                event="notification.created",
                message=data.message,
                data=data,
            )
        except ValidationError:
            return 0
        if not await self._claim(notification_id):
            return 0
        return await self._manager.publish(item.user_id, event.model_dump(mode="json"))


realtime_notification_publisher = RealtimeNotificationPublisher(
    manager=notification_connection_manager,
    session_factory=AsyncSessionLocal,
)
