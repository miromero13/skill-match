"""Post-commit native push dispatch for new in-app notifications (single choke point).

`NotificationService.emit_in_app` records every NEW notification it inserts on the
session (`session.info`), tagged with the innermost transaction that created it.
Session events then:

- `after_commit` (outermost commit only): schedule one background dispatch per pending
  notification; each dispatch opens its own DB session, so it never runs inside (nor
  delays, nor fails) the originating transaction/request.
- `after_soft_rollback`: drop entries created inside the rolled-back (sub)transaction.
- `after_transaction_end` of the outermost transaction: drop leftovers (closed sessions).

Replays never record (emit_in_app returns the existing row without inserting). Tests can
replace `dispatch_hook` and await `drain()` for deterministic completion.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, SessionTransaction

logger = logging.getLogger("skillmatch.push_dispatch")

_PENDING_KEY = "skillmatch_pending_native_push"


@dataclass(frozen=True)
class PendingPush:
    notification_id: UUID
    user_id: UUID
    notification_type: str
    title: str
    message: str
    transaction: Any = field(default=None, compare=False, repr=False)


async def dispatch_notification_push(item: PendingPush) -> None:
    """Push one committed notification when its category is enabled for the recipient.

    Gate is the category flag only (S4 amendment / L4): the `push` channel toggle defaults
    to False and is deliberately not consulted. Unknown types or inactive recipients raise
    and are swallowed by `_run` (no push).
    """
    from app.db.session import BackgroundSessionLocal
    from app.services.fcm_service import FCMService
    from app.services.notification_service import NotificationService

    async with BackgroundSessionLocal() as db:
        if not await NotificationService.category_enabled(db, item.user_id, item.notification_type):
            return
        await FCMService.send_push_to_user(
            db,
            user_id=item.user_id,
            title=item.title,
            body=item.message,
            data={"type": item.notification_type, "notification_id": str(item.notification_id)},
        )
        await db.rollback()  # read-only session; nothing of the caller is ever committed here


dispatch_hook: Callable[[PendingPush], Awaitable[None]] = dispatch_notification_push

_tasks: set[asyncio.Task[None]] = set()


async def _run(item: PendingPush) -> None:
    try:
        await dispatch_hook(item)
    except Exception as exc:  # noqa: BLE001 — background push must never surface errors
        logger.warning(
            "Push nativo no despachado para la notificación %s: %s", item.notification_id, type(exc).__name__,
        )


def schedule_dispatch(items: list[PendingPush]) -> list[asyncio.Task[None]]:
    """Schedule background dispatch; keeps strong references until each task finishes."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.warning("Sin event loop activo: %d push(es) nativo(s) no despachado(s).", len(items))
        return []
    scheduled = []
    for item in items:
        task = loop.create_task(_run(item))
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)
        scheduled.append(task)
    return scheduled


async def drain() -> None:
    """Await every scheduled dispatch (tests / graceful shutdown)."""
    while _tasks:
        await asyncio.gather(*list(_tasks), return_exceptions=True)


def record_new_notification(db: AsyncSession | Session, notification: Any) -> None:
    """Called by emit_in_app for a NEW row only; dispatch happens after the outermost commit."""
    sync_session = db.sync_session if isinstance(db, AsyncSession) else db
    transaction = sync_session.get_nested_transaction() or sync_session.get_transaction()
    sync_session.info.setdefault(_PENDING_KEY, []).append(PendingPush(
        notification_id=notification.id,
        user_id=notification.user_id,
        notification_type=str(notification.type),
        title=notification.title,
        message=notification.message,
        transaction=transaction,
    ))


def _within(transaction: SessionTransaction | None, ancestor: SessionTransaction) -> bool:
    while transaction is not None:
        if transaction is ancestor:
            return True
        transaction = transaction.parent
    return False


def _after_commit(session: Session) -> None:
    pending = session.info.pop(_PENDING_KEY, None)
    if pending:
        schedule_dispatch(pending)


def _after_soft_rollback(session: Session, previous_transaction: SessionTransaction) -> None:
    pending = session.info.get(_PENDING_KEY)
    if pending:
        session.info[_PENDING_KEY] = [p for p in pending if not _within(p.transaction, previous_transaction)]


def _after_transaction_end(session: Session, transaction: SessionTransaction) -> None:
    if transaction.parent is None:
        session.info.pop(_PENDING_KEY, None)


def register_push_dispatch_events() -> None:
    """Idempotent global registration on every ORM Session."""
    for name, listener in (
        ("after_commit", _after_commit),
        ("after_soft_rollback", _after_soft_rollback),
        ("after_transaction_end", _after_transaction_end),
    ):
        if not event.contains(Session, name, listener):
            event.listen(Session, name, listener)


register_push_dispatch_events()
