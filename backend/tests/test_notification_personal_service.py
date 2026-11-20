import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import event, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.exceptions import SkillMatchException
from app.models.notification import Notification
from app.models.notification_preference import NotificationPreference
from app.schemas.notification import NotificationFilters, NotificationPreferencesWrite
from app.services.notification_service import NotificationService
from test_notification_persistence import persistence  # noqa: F401
from test_notifications import DEFAULTS, inbox, seed  # noqa: F401

pytestmark = pytest.mark.hu25


def preference_payload(revision=0, **channel_changes):
    data = deepcopy(DEFAULTS)
    data["revision"] = revision
    data["channels"].update(channel_changes)
    return NotificationPreferencesWrite.model_validate(data)


@pytest.mark.parametrize("owner", [0, 2])
async def test_personal_lifecycle_for_member_and_admin(inbox, owner):
    item = await seed(inbox, owner=owner)
    inbox.db.autoflush = False
    rows, total = await NotificationService.list_owned(inbox.db, inbox.users[owner].id, NotificationFilters())
    assert total == 1 and rows[0].id == item.id
    first = await NotificationService.mark_read(inbox.db, inbox.users[owner].id, item.id)
    second = await NotificationService.mark_read(inbox.db, inbox.users[owner].id, item.id)
    assert first.read_at is not None and second.read_at == first.read_at
    await NotificationService.delete_owned(inbox.db, inbox.users[owner].id, item.id)
    rows, total = await NotificationService.list_owned(inbox.db, inbox.users[owner].id, NotificationFilters())
    assert rows == [] and total == 0
    await inbox.db.refresh(item)
    assert item.deleted_at is not None
    for method in [NotificationService.mark_read, NotificationService.delete_owned]:
        with pytest.raises(SkillMatchException) as failure:
            await method(inbox.db, inbox.users[owner].id, item.id)
        assert failure.value.statuscode == 404


@pytest.mark.parametrize("actor", [1, 2])
async def test_other_member_or_admin_has_no_access_to_personal_items(inbox, actor):
    item = await seed(inbox)
    user = inbox.users[actor].id
    rows, total = await NotificationService.list_owned(inbox.db, user, NotificationFilters())
    assert rows == [] and total == 0
    for method in [NotificationService.mark_read, NotificationService.delete_owned]:
        with pytest.raises(SkillMatchException) as failure:
            await method(inbox.db, user, item.id)
        assert failure.value.statuscode == 404 and failure.value.message == "Recurso no encontrado"
    await NotificationService.mark_all_read(inbox.db, user)
    await inbox.db.refresh(item)
    assert item.read_at is item.deleted_at is None


@pytest.mark.parametrize("method", ["mark_read", "delete_owned"])
async def test_missing_resource_is_404(inbox, method):
    with pytest.raises(SkillMatchException) as failure:
        await getattr(NotificationService, method)(inbox.db, inbox.users[0].id, uuid4())
    assert failure.value.statuscode == 404


async def test_filters_pagination_and_count_share_one_statement_snapshot(inbox):
    now = datetime.now(timezone.utc)
    old = await seed(inbox, created_at=now - timedelta(minutes=2))
    points = await seed(inbox, type="POINTS_RECEIVED", created_at=now - timedelta(minutes=1))
    await seed(inbox, type="OTHER", read_at=now, created_at=now)
    await seed(inbox, deleted_at=now)
    await seed(inbox, owner=1)
    statements = []

    def capture(connection, cursor, statement, parameters, context, many):
        # The rollback harness creates a request SAVEPOINT on first use. It is
        # transaction control, not a second read of the notification population.
        if statement.lstrip().upper().startswith(("SELECT", "WITH")):
            statements.append(statement)

    engine = inbox.db.bind.engine.sync_engine
    event.listen(engine, "before_cursor_execute", capture)
    try:
        rows, total = await NotificationService.list_owned(inbox.db, inbox.users[0].id, NotificationFilters(page=2, page_size=1))
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert len(statements) == 1
    assert total == 3 and [row.id for row in rows] == [points.id]
    for filters, expected in [(NotificationFilters(unread=True, page_size=1), 2),
                              (NotificationFilters(unread=False), 1),
                              (NotificationFilters(category="POINTS", unread=True), 1),
                              (NotificationFilters(category="INTERCHANGES"), 1)]:
        rows, total = await NotificationService.list_owned(inbox.db, inbox.users[0].id, filters)
        assert total == expected
        assert all(set(row.model_dump()) == {"id", "type", "category", "title", "message", "created_at", "read_at"} for row in rows)
    rows, total = await NotificationService.list_owned(inbox.db, inbox.users[0].id, NotificationFilters(page=999))
    assert rows == [] and total == 3
    await NotificationService.delete_owned(inbox.db, inbox.users[0].id, old.id)
    _, total = await NotificationService.list_owned(inbox.db, inbox.users[0].id, NotificationFilters(unread=True))
    assert total == 1


async def test_uuid_breaks_creation_time_ties(inbox):
    now = datetime.now(timezone.utc)
    items = [await seed(inbox, created_at=now) for _ in range(3)]
    rows, total = await NotificationService.list_owned(inbox.db, inbox.users[0].id, NotificationFilters())
    assert total == 3 and [row.id for row in rows] == sorted(item.id for item in items)


@pytest.mark.parametrize("page", [2**40, 10**100])
async def test_very_large_out_of_range_page_is_empty_not_a_database_error(inbox, page):
    await seed(inbox)
    rows, total = await NotificationService.list_owned(inbox.db, inbox.users[0].id, NotificationFilters(page=page))
    assert rows == [] and total == 1


async def test_mark_all_preserves_old_reads_and_ignores_deleted_or_foreign(inbox):
    now = datetime.now(timezone.utc) - timedelta(days=1)
    old = await seed(inbox, read_at=now)
    unread = await seed(inbox)
    deleted = await seed(inbox, deleted_at=now)
    other = await seed(inbox, owner=1)
    assert await NotificationService.mark_all_read(inbox.db, inbox.users[0].id) is None
    for item in [old, unread, deleted, other]:
        await inbox.db.refresh(item)
    assert old.read_at == now and unread.read_at is not None
    assert deleted.read_at is other.read_at is None
    first = unread.read_at
    await NotificationService.mark_all_read(inbox.db, inbox.users[0].id)
    await inbox.db.refresh(unread)
    assert unread.read_at == first


@pytest.mark.parametrize("owner", [0, 2])
async def test_preference_revisions_and_isolation(inbox, owner):
    user = inbox.users[owner].id
    assert (await NotificationService.get_preferences(inbox.db, user)).revision == 0
    saved = await NotificationService.update_preferences(inbox.db, user, preference_payload(push=True))
    assert saved.revision == 1 and saved.channels.push
    next_value = await NotificationService.update_preferences(inbox.db, user, preference_payload(1, email=True))
    assert next_value.revision == 2 and next_value.channels.email and not next_value.channels.push
    assert (await NotificationService.get_preferences(inbox.db, user)).model_dump() == next_value.model_dump()
    with pytest.raises(SkillMatchException) as failure:
        await NotificationService.update_preferences(inbox.db, user, preference_payload(1))
    assert failure.value.statuscode == 409
    assert failure.value.message == "Las preferencias cambiaron. Recarga la configuración antes de guardar."
    assert (await NotificationService.get_preferences(inbox.db, inbox.users[1].id)).revision == 0


@pytest.mark.parametrize("revision", [1, 99, 2**40])
async def test_missing_preferences_cannot_be_updated_with_nonzero_revision(inbox, revision):
    with pytest.raises(SkillMatchException) as failure:
        await NotificationService.update_preferences(inbox.db, inbox.users[0].id, preference_payload(revision))
    assert failure.value.statuscode == 409
    assert await inbox.db.scalar(text("SELECT count(*) FROM notification_preferences WHERE user_id=:id"), {"id": inbox.users[0].id}) == 0


@pytest.fixture
async def pool(persistence):
    connection, schema, users, _ = persistence
    await connection.commit()
    engine = create_async_engine(settings.async_database_url, isolation_level="READ COMMITTED",
        connect_args={"server_settings": {"search_path": schema}})
    try:
        yield async_sessionmaker(engine, expire_on_commit=False, autoflush=False), users
    finally:
        await engine.dispose()


@pytest.mark.parametrize("revision", [0, 1])
async def test_simultaneous_preference_updates_have_exactly_one_winner(pool, revision):
    sessions, users = pool
    if revision:
        async with sessions() as db:
            await NotificationService.update_preferences(db, users[0], preference_payload())
            await db.commit()

    async def update(push):
        async with sessions() as db:
            try:
                result = await NotificationService.update_preferences(db, users[0], preference_payload(revision, push=push))
                await db.commit()
                return result
            except SkillMatchException as exc:
                await db.rollback()
                return exc

    outcomes = await asyncio.gather(update(True), update(False))
    winners = [value for value in outcomes if not isinstance(value, SkillMatchException)]
    conflicts = [value for value in outcomes if isinstance(value, SkillMatchException)]
    assert len(winners) == len(conflicts) == 1 and conflicts[0].statuscode == 409
    async with sessions() as db:
        actual = await NotificationService.get_preferences(db, users[0])
        assert actual.model_dump() == winners[0].model_dump() and actual.revision == revision + 1


async def notice(sessions, user):
    async with sessions() as db:
        item = await NotificationService.emit_in_app(db, user_id=user, event_id=uuid4(), notification_type="OTHER", title="Title", message="Message")
        await db.commit()
        return item.id


async def test_concurrent_mark_read_preserves_one_timestamp(pool):
    sessions, users = pool
    identifier = await notice(sessions, users[0])

    async def read():
        async with sessions() as db:
            result = await NotificationService.mark_read(db, users[0], identifier)
            await db.commit()
            return result.read_at

    timestamps = await asyncio.gather(read(), read())
    assert timestamps[0] is not None and timestamps[0] == timestamps[1]


async def test_read_racing_with_delete_never_resurrects_notice(pool):
    sessions, users = pool
    identifier = await notice(sessions, users[0])

    async def read():
        async with sessions() as db:
            try:
                result = await NotificationService.mark_read(db, users[0], identifier)
                await db.commit()
                return result
            except SkillMatchException as exc:
                await db.rollback()
                assert exc.statuscode == 404
                return None

    async def delete():
        async with sessions() as db:
            await NotificationService.delete_owned(db, users[0], identifier)
            await db.commit()

    await asyncio.gather(read(), delete())
    async with sessions() as db:
        assert (await db.get(Notification, identifier)).deleted_at is not None
        assert await NotificationService.list_owned(db, users[0], NotificationFilters()) == ([], 0)


async def test_mark_all_statement_snapshot_excludes_later_committed_insert(pool):
    sessions, users = pool
    identifier = await notice(sessions, users[0])
    ready = asyncio.Event()
    worker_pid = []
    async with sessions() as locker:
        locker_pid = await locker.scalar(text("SELECT pg_backend_pid()"))
        await locker.execute(select(Notification.id).where(Notification.id == identifier).with_for_update())

        async def mark():
            async with sessions() as db:
                worker_pid.append(await db.scalar(text("SELECT pg_backend_pid()")))
                ready.set()
                await NotificationService.mark_all_read(db, users[0])
                await db.commit()

        task = asyncio.create_task(mark())
        try:
            await asyncio.wait_for(ready.wait(), 5)
            # Observe a real PostgreSQL lock wait: no sleep-based guess about when
            # the UPDATE acquired its statement snapshot.
            async with sessions() as monitor:
                async with asyncio.timeout(5):
                    while True:
                        if task.done():
                            await task
                            raise AssertionError("UPDATE did not block on the old notice")
                        blocked = await monitor.scalar(text("SELECT :locker = ANY(pg_blocking_pids(:worker))"),
                            {"locker": locker_pid, "worker": worker_pid[0]})
                        if blocked:
                            break
                        await asyncio.sleep(0.02)
            later = await notice(sessions, users[0])
            await locker.commit()
            await asyncio.wait_for(task, 5)
            async with sessions() as db:
                assert (await db.get(Notification, identifier)).read_at is not None
                assert (await db.get(Notification, later)).read_at is None
        finally:
            await locker.rollback()
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass


async def test_service_writes_remain_reversible_by_caller(pool):
    sessions, users = pool
    identifier = await notice(sessions, users[0])
    async with sessions() as db:
        await NotificationService.mark_read(db, users[0], identifier)
        await NotificationService.delete_owned(db, users[0], identifier)
        await NotificationService.update_preferences(db, users[0], preference_payload(push=True))
        await db.rollback()
    async with sessions() as db:
        item = await db.get(Notification, identifier)
        assert item.read_at is item.deleted_at is None
        assert await db.get(NotificationPreference, users[0]) is None
