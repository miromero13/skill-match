"""HU-25 inbox domain. Caller supplies the authorized user's ID and owns commit.

No WebSocket, push/email dispatch, broker or public creation endpoint lives here.
"""
from uuid import UUID

from sqlalchemy import BigInteger, func, literal, select, true, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.exceptions import SkillMatchException
from app.models.notification import NOTIFICATION_CATEGORIES, Notification, NotificationType
from app.models.notification_preference import NotificationPreference
from app.models.user import User
from app.schemas.notification import (
    NotificationCategories, NotificationChannels, NotificationEmission,
    NotificationFilters, NotificationPreferencesResponse, NotificationPreferencesWrite,
    NotificationResponse,
)


class NotificationService:
    @staticmethod
    async def _ensure_recipient(db: AsyncSession, user_id: UUID) -> None:
        recipient = await db.scalar(select(User.id).where(
            User.id == user_id, User.is_active.is_(True), User.is_locked.is_(False),
        ))
        if recipient is None:
            raise SkillMatchException("Recurso no encontrado", statuscode=404)

    @staticmethod
    async def get_preferences(db: AsyncSession, user_id: UUID) -> NotificationPreferencesResponse:
        """Effective values only; caller authorizes user_id, no insertion on read."""
        prefs = await db.scalar(select(NotificationPreference).where(
            NotificationPreference.user_id == user_id,
        ).execution_options(populate_existing=True))
        if prefs is None:
            return NotificationPreferencesResponse.defaults()
        return NotificationService._serialize_preferences(prefs)

    @staticmethod
    def _serialize_preferences(prefs: NotificationPreference) -> NotificationPreferencesResponse:
        return NotificationPreferencesResponse(
            revision=prefs.revision,
            channels=NotificationChannels(in_app=prefs.in_app, push=prefs.push, email=prefs.email),
            categories=NotificationCategories(
                INTERCHANGES=prefs.interchanges, POINTS=prefs.points, GENERAL=prefs.general,
            ),
        )

    @staticmethod
    async def list_owned(
        db: AsyncSession, user_id: UUID, filters: NotificationFilters | None = None,
    ) -> tuple[list[NotificationResponse], int]:
        filters = NotificationFilters.model_validate(filters or {})
        await db.flush()
        conditions = [Notification.user_id == user_id, Notification.deleted_at.is_(None)]
        if filters.unread is not None:
            conditions.append(Notification.read_at.is_(None) if filters.unread else Notification.read_at.is_not(None))
        if filters.category is not None:
            kinds = [kind.value for kind, category in NOTIFICATION_CATEGORIES.items() if category == filters.category]
            conditions.append(Notification.type.in_(kinds))
        visible = select(Notification).where(*conditions).cte("visible_notifications")
        total = select(func.count().label("total")).select_from(visible).cte("notification_total")
        # Arbitrarily large out-of-range pages are still empty pages, not int8
        # binding errors. PostgreSQL row counts/offsets cannot exceed int8.
        offset = min((filters.page - 1) * filters.page_size, 9_223_372_036_854_775_807)
        page = select(visible).order_by(visible.c.created_at.desc(), visible.c.id.asc()).offset(
            literal(offset, type_=BigInteger()),
        ).limit(filters.page_size).cte("notification_page")
        item = aliased(Notification, page)
        # Outer join retains the total even on an empty/out-of-range page. Both
        # rows and count use the same statement snapshot, never two racing reads.
        result = await db.execute(select(item, total.c.total).select_from(
            total.outerjoin(page, true()),
        ).order_by(page.c.created_at.desc(), page.c.id.asc()).execution_options(populate_existing=True))
        rows = result.all()
        return [NotificationResponse.model_validate(row[0]) for row in rows if row[0] is not None], int(rows[0][1])

    @staticmethod
    async def mark_read(db: AsyncSession, user_id: UUID, notification_id: UUID) -> NotificationResponse:
        await db.flush()
        item = await db.scalar(update(Notification).where(
            Notification.id == notification_id, Notification.user_id == user_id,
            Notification.deleted_at.is_(None),
        ).values(read_at=func.coalesce(Notification.read_at, func.statement_timestamp())).returning(
            Notification,
        ).execution_options(populate_existing=True))
        if item is None:
            raise SkillMatchException("Recurso no encontrado", statuscode=404)
        return NotificationResponse.model_validate(item)

    @staticmethod
    async def mark_all_read(db: AsyncSession, user_id: UUID) -> None:
        await db.flush()
        await db.execute(update(Notification).where(
            Notification.user_id == user_id, Notification.deleted_at.is_(None),
            Notification.read_at.is_(None),
        ).values(read_at=func.statement_timestamp()).execution_options(synchronize_session=False))

    @staticmethod
    async def delete_owned(db: AsyncSession, user_id: UUID, notification_id: UUID) -> None:
        await db.flush()
        identifier = await db.scalar(update(Notification).where(
            Notification.id == notification_id, Notification.user_id == user_id,
            Notification.deleted_at.is_(None),
        ).values(deleted_at=func.statement_timestamp()).returning(Notification.id).execution_options(synchronize_session=False))
        if identifier is None:
            raise SkillMatchException("Recurso no encontrado", statuscode=404)

    @staticmethod
    async def update_preferences(
        db: AsyncSession, user_id: UUID, payload: NotificationPreferencesWrite,
    ) -> NotificationPreferencesResponse:
        payload = NotificationPreferencesWrite.model_validate(payload)
        await db.flush()
        await NotificationService._ensure_recipient(db, user_id)
        values = {
            **payload.channels.model_dump(),
            "interchanges": payload.categories.INTERCHANGES,
            "points": payload.categories.POINTS,
            "general": payload.categories.GENERAL,
        }
        if payload.revision == 0:
            statement = insert(NotificationPreference).values(user_id=user_id, revision=1, **values).on_conflict_do_nothing(
                index_elements=[NotificationPreference.user_id],
            ).returning(NotificationPreference)
        elif payload.revision < 2_147_483_647:
            statement = update(NotificationPreference).where(
                NotificationPreference.user_id == user_id,
                NotificationPreference.revision == payload.revision,
            ).values(revision=NotificationPreference.revision + 1, updated_at=func.statement_timestamp(), **values).returning(NotificationPreference)
        else:
            # Avoid PostgreSQL int4 binding/increment overflow on an impossible
            # client revision; it is a conflict, not an internal database error.
            statement = None
        prefs = await db.scalar(statement.execution_options(populate_existing=True)) if statement is not None else None
        if prefs is None:
            raise SkillMatchException(
                "Las preferencias cambiaron. Recarga la configuración antes de guardar.", statuscode=409,
            )
        return NotificationService._serialize_preferences(prefs)

    @staticmethod
    def _effective_channels(prefs: NotificationPreferencesResponse, kind: NotificationType) -> NotificationChannels:
        enabled = getattr(prefs.categories, NOTIFICATION_CATEGORIES[kind].value)
        return NotificationChannels(
            in_app=enabled and prefs.channels.in_app,
            push=enabled and prefs.channels.push,
            email=enabled and prefs.channels.email,
        )

    @staticmethod
    async def resolve_channels(db: AsyncSession, user_id: UUID, notification_type: NotificationType | str) -> NotificationChannels:
        """Preferences indicate eligibility, never proof of delivery or OS permission."""
        kind = NotificationType(notification_type)
        await db.flush()
        await NotificationService._ensure_recipient(db, user_id)
        prefs = await NotificationService.get_preferences(db, user_id)
        return NotificationService._effective_channels(prefs, kind)

    @staticmethod
    async def _existing(db: AsyncSession, payload: NotificationEmission) -> Notification | None:
        # Include tombstones: replay must never resurrect an erased inbox item.
        return await db.scalar(select(Notification).where(
            Notification.user_id == payload.user_id, Notification.event_id == payload.event_id,
        ).execution_options(populate_existing=True))

    @staticmethod
    def _same_event(item: Notification, payload: NotificationEmission) -> Notification:
        if (item.type, item.title, item.message) != (payload.notification_type.value, payload.title, payload.message):
            raise SkillMatchException("El evento ya fue registrado con contenido diferente.", statuscode=409)
        return item

    @staticmethod
    async def emit_in_app(
        db: AsyncSession, *, user_id: UUID, event_id: UUID,
        notification_type: NotificationType | str, title: str, message: str,
    ) -> Notification | None:
        """Return the stored identity or None when new in-app emission is suppressed.

        Result is internal ORM, possibly a tombstone on replay; never serialize a
        tombstone publicly. No commit occurs here. Producers own stable event_id,
        caller transaction and future transport publication after successful commit.
        Suppressed attempts are not recorded or retroactively reissued.
        """
        payload = NotificationEmission(user_id=user_id, event_id=event_id,
            notification_type=notification_type, title=title, message=message)
        # Production disables autoflush. Respect the caller's pending preference
        # changes/tombstones before refreshing identities; never commit them here.
        await db.flush()
        await NotificationService._ensure_recipient(db, payload.user_id)
        existing = await NotificationService._existing(db, payload)
        if existing is not None:
            return NotificationService._same_event(existing, payload)
        prefs = await NotificationService.get_preferences(db, payload.user_id)
        if not NotificationService._effective_channels(prefs, payload.notification_type).in_app:
            return None
        statement = insert(Notification).values(
            user_id=payload.user_id, event_id=payload.event_id, type=payload.notification_type.value,
            title=payload.title, message=payload.message,
        ).on_conflict_do_nothing(constraint="uq_notifications_user_event").returning(Notification)
        inserted = await db.scalar(statement)
        if inserted is not None:
            return inserted
        # Concurrent winner is visible in the next READ COMMITTED statement.
        winner = await NotificationService._existing(db, payload)
        if winner is None:
            raise SkillMatchException("El estado del evento cambió. Reintenta la operación.", statuscode=409)
        return NotificationService._same_event(winner, payload)
