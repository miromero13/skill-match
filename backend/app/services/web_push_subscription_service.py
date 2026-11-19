"""Persistence boundary for private Web Push device subscriptions."""

from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import SkillMatchException
from app.models.web_push_subscription import WebPushSubscription
from app.schemas.web_push import WebPushSubscriptionCreate, WebPushSubscriptionResponse


class WebPushSubscriptionService:
    @staticmethod
    def endpoint_hash(endpoint: str) -> str:
        return sha256(endpoint.encode("utf-8")).hexdigest()

    @staticmethod
    def _response(item: WebPushSubscription) -> WebPushSubscriptionResponse:
        return WebPushSubscriptionResponse(
            id=item.id,
            endpoint=f"sha256:{item.endpoint_hash[:16]}",
            device_label=item.device_label,
            is_active=item.is_active,
            created_at=item.created_at,
        )

    @classmethod
    async def register(
        cls,
        db: AsyncSession,
        *,
        user_id: UUID,
        payload: WebPushSubscriptionCreate,
    ) -> tuple[WebPushSubscriptionResponse, bool]:
        digest = cls.endpoint_hash(payload.endpoint)
        statement = (
            insert(WebPushSubscription)
            .values(
                user_id=user_id,
                endpoint=payload.endpoint,
                endpoint_hash=digest,
                p256dh=payload.keys.p256dh,
                auth=payload.keys.auth,
                device_label=payload.device_label,
                is_active=True,
            )
            .on_conflict_do_nothing(index_elements=[WebPushSubscription.endpoint_hash])
            .returning(WebPushSubscription)
        )
        item = await db.scalar(statement)
        if item is not None:
            return cls._response(item), True

        existing = await db.scalar(
            select(WebPushSubscription)
            .where(WebPushSubscription.endpoint_hash == digest)
            .with_for_update()
        )
        if existing is None:
            raise SkillMatchException(
                "No fue posible registrar la suscripción push.", statuscode=409,
            )
        if existing.user_id != user_id:
            raise SkillMatchException(
                "La suscripción ya está registrada.", statuscode=409,
            )

        existing.endpoint = payload.endpoint
        existing.p256dh = payload.keys.p256dh
        existing.auth = payload.keys.auth
        existing.device_label = payload.device_label
        existing.is_active = True
        existing.revoked_at = None
        existing.updated_at = datetime.now(UTC)
        await db.flush()
        return cls._response(existing), False

    @classmethod
    async def revoke(cls, db: AsyncSession, *, user_id: UUID, subscription_id: UUID) -> None:
        identifier = await db.scalar(
            update(WebPushSubscription)
            .where(
                WebPushSubscription.id == subscription_id,
                WebPushSubscription.user_id == user_id,
                WebPushSubscription.is_active.is_(True),
            )
            .values(
                is_active=False,
                revoked_at=func.statement_timestamp(),
                updated_at=func.statement_timestamp(),
            )
            .returning(WebPushSubscription.id)
            .execution_options(synchronize_session=False)
        )
        if identifier is None:
            raise SkillMatchException("Recurso no encontrado", statuscode=404)
