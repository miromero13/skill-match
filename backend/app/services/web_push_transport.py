"""Local VAPID transport adapter for browser Web Push."""

import asyncio

from pywebpush import WebPushException, webpush  # type: ignore[import-untyped]

from app.models.web_push_subscription import WebPushSubscription
from app.services.session_web_push_service import SessionReminderPushPayload


class PyWebPushSender:
    def __init__(self, *, private_key: str, subject: str, timeout_seconds: int = 15) -> None:
        self._private_key = private_key
        self._subject = subject
        self._timeout_seconds = timeout_seconds

    async def send(
        self,
        subscription: WebPushSubscription,
        payload: SessionReminderPushPayload,
    ) -> int:
        def send_sync() -> int:
            try:
                response = webpush(
                    subscription_info={
                        "endpoint": subscription.endpoint,
                        "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
                    },
                    data=payload.to_json(),
                    vapid_private_key=self._private_key,
                    vapid_claims={"sub": self._subject},
                    timeout=self._timeout_seconds,
                )
            except WebPushException as exc:
                if exc.response is not None:
                    return int(exc.response.status_code)
                raise OSError("Web Push transport failed without HTTP response") from exc
            return int(response.status_code)

        return await asyncio.to_thread(send_sync)
