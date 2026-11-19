import asyncio
import logging
from datetime import UTC, datetime

from app.core.celery_app import celery_app
from app.core.config import settings
from app.db.session import AsyncSessionLocal, async_engine
from app.services.email_service import SMTPEmailSender
from app.services.realtime_notification_broker import publish_notification_ids
from app.services.session_reminder_email_delivery_service import (
    EmailDeliveryResult,
    deliver_pending_reminder_emails,
)
from app.services.session_reminder_service import dispatch_due_reminders
from app.services.session_reminder_web_push_delivery_service import (
    WebPushDeliveryResult,
    deliver_pending_reminder_web_push,
)
from app.services.web_push_transport import PyWebPushSender

logger = logging.getLogger("skillmatch.sessions.reminders")


async def _dispatch() -> dict[str, int]:
    now = datetime.now(UTC)
    async with AsyncSessionLocal() as db:
        try:
            notification_ids = await dispatch_due_reminders(db, now=now)
            await db.commit()
        except Exception:
            await db.rollback()
            raise
    subscribers = 0
    if notification_ids:
        try:
            subscribers = await publish_notification_ids(notification_ids)
        except Exception:
            logger.exception("Reminders persisted but realtime broker publication failed")
    email_result = EmailDeliveryResult()
    username = settings.SMTP_USERNAME.get_secret_value() if settings.SMTP_USERNAME else ""
    password = settings.SMTP_PASSWORD.get_secret_value() if settings.SMTP_PASSWORD else ""
    from_address = settings.EMAIL_FROM_ADDRESS or ""
    if settings.EMAIL_ENABLED and username and password and from_address:
        sender = SMTPEmailSender(
            host=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=username,
            password=password,
            starttls=settings.SMTP_STARTTLS,
            timeout_seconds=settings.SMTP_TIMEOUT_SECONDS,
            from_address=from_address,
            from_name=settings.EMAIL_FROM_NAME,
            reply_to=settings.EMAIL_REPLY_TO,
        )
        async with AsyncSessionLocal() as db:
            try:
                email_result = await deliver_pending_reminder_emails(
                    db,
                    sender=sender,
                    now=now,
                    sessions_url=f"{settings.FRONTEND_BASE_URL.rstrip('/')}/app/sessions",
                )
                await db.commit()
            except Exception:
                await db.rollback()
                logger.exception("Unexpected reminder email delivery failure")
    elif settings.EMAIL_ENABLED:
        logger.error("Email delivery is enabled but SMTP credentials are incomplete")
    push_result = WebPushDeliveryResult()
    private_key = (
        settings.VAPID_PRIVATE_KEY.get_secret_value()
        if settings.VAPID_PRIVATE_KEY else ""
    )
    if (
        settings.WEB_PUSH_ENABLED
        and settings.VAPID_PUBLIC_KEY
        and private_key
        and settings.VAPID_SUBJECT
    ):
        sender = PyWebPushSender(
            private_key=private_key,
            subject=settings.VAPID_SUBJECT,
        )
        async with AsyncSessionLocal() as db:
            try:
                push_result = await deliver_pending_reminder_web_push(
                    db, sender=sender, now=now,
                )
                await db.commit()
            except Exception:
                await db.rollback()
                logger.exception("Unexpected Web Push reminder delivery failure")
    elif settings.WEB_PUSH_ENABLED:
        logger.error("Web Push is enabled but VAPID configuration is incomplete")
    return {
        "notifications_created": len(notification_ids),
        "broker_subscribers": subscribers,
        "emails_sent": email_result.sent,
        "emails_failed": email_result.failed,
        "emails_skipped": email_result.skipped,
        "push_sent": push_result.sent,
        "push_failed": push_result.failed,
        "push_skipped": push_result.skipped,
    }


@celery_app.task(name="sessions.dispatch_due_reminders")
def dispatch_session_reminders() -> dict[str, int]:
    async def run_once() -> dict[str, int]:
        try:
            return await _dispatch()
        finally:
            # A Celery worker invokes this sync task through a fresh asyncio.run loop.
            # Never retain asyncpg pooled connections bound to a loop that is about to close.
            await async_engine.dispose()

    return asyncio.run(run_once())
