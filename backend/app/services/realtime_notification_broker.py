import asyncio
import logging
from collections.abc import Iterable
from uuid import UUID

from redis.asyncio import Redis

from app.core.config import settings
from app.services.realtime_notification_publisher import realtime_notification_publisher

logger = logging.getLogger("skillmatch.notifications.broker")
NOTIFICATION_CHANNEL = "skillmatch:notification-committed"


async def publish_notification_ids(notification_ids: Iterable[UUID]) -> int:
    client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    published = 0
    try:
        for notification_id in notification_ids:
            published += int(await client.publish(NOTIFICATION_CHANNEL, str(notification_id)))
    finally:
        await client.aclose()
    return published


async def consume_notification_events() -> None:
    """Bridge committed notification IDs from Celery/Redis to local WebSockets."""
    while True:
        client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
        pubsub = client.pubsub()
        try:
            await pubsub.subscribe(NOTIFICATION_CHANNEL)
            async for event in pubsub.listen():
                if event.get("type") != "message":
                    continue
                try:
                    notification_id = UUID(str(event.get("data")))
                except (TypeError, ValueError):
                    logger.warning("Ignored invalid notification broker payload")
                    continue
                await realtime_notification_publisher.publish_committed(notification_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Notification broker unavailable; reconnecting")
            await asyncio.sleep(5)
        finally:
            await pubsub.aclose()
            await client.aclose()
