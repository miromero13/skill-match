import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from pydantic import ValidationError
import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.exceptions import SkillMatchException
from app.models.notification import Notification
from app.models.notification_preference import NotificationPreference
from test_notifications import inbox  # noqa: F401 — shared real-JWT transaction fixture
from test_notification_persistence import persistence  # noqa: F401

pytestmark = pytest.mark.hu25


async def emit(api, **changes):
    from app.services.notification_service import NotificationService
    return await NotificationService.emit_in_app(api.db, user_id=changes.pop("user_id", api.users[0].id),
        event_id=changes.pop("event_id", uuid4()), notification_type=changes.pop("notification_type", "MATCH_RECEIVED"),
        title=changes.pop("title", " Title "), message=changes.pop("message", " Message "), **changes)


async def test_defaults_read_and_channel_resolution_never_materialize_preferences(inbox):
    from app.services.notification_service import NotificationService
    prefs = await NotificationService.get_preferences(inbox.db, inbox.users[0].id)
    assert prefs.revision == 0 and prefs.channels.in_app and not prefs.channels.push
    channels = await NotificationService.resolve_channels(inbox.db, inbox.users[0].id, "OTHER")
    assert channels.model_dump() == {"in_app": True, "push": False, "email": False}
    assert await inbox.db.scalar(text("SELECT count(*) FROM notification_preferences WHERE user_id=:id"), {"id": inbox.users[0].id}) == 0


@pytest.mark.parametrize("owner", [0, 2])
async def test_emission_uses_existing_transaction_and_normalizes_content(inbox, owner):
    item = await emit(inbox, user_id=inbox.users[owner].id)
    assert item.user_id == inbox.users[owner].id and item.title == "Title" and item.message == "Message"
    assert item.read_at is item.deleted_at is None
    assert await inbox.db.scalar(select(Notification.id).where(Notification.id == item.id)) == item.id


@pytest.mark.parametrize("kind,category", [
    ("MATCH_RECEIVED", "INTERCHANGES"), ("MATCH_CONFIRMED", "INTERCHANGES"),
    ("SESSION_PROPOSED", "INTERCHANGES"), ("POINTS_RECEIVED", "POINTS"), ("OTHER", "GENERAL"),
])
async def test_emission_derives_category(inbox, kind, category):
    assert (await emit(inbox, notification_type=kind)).category == category


@pytest.mark.parametrize("disabled,kind", [("in_app", "OTHER"), ("interchanges", "MATCH_RECEIVED"), ("points", "POINTS_RECEIVED"), ("general", "OTHER")])
async def test_disabled_channels_or_categories_suppress_only_new_notices(inbox, disabled, kind):
    from app.services.notification_service import NotificationService
    original = await emit(inbox)
    prefs = NotificationPreference(user_id=inbox.users[0].id)
    setattr(prefs, disabled, False)
    inbox.db.add(prefs)
    await inbox.db.flush()
    assert await emit(inbox, notification_type=kind) is None
    assert await inbox.db.scalar(select(Notification.id).where(Notification.id == original.id)) == original.id
    if disabled != "in_app":
        prefs.push = prefs.email = True
        await inbox.db.flush()
        channels = await NotificationService.resolve_channels(inbox.db, inbox.users[0].id, kind)
        assert channels.model_dump() == {"in_app": False, "push": False, "email": False}


async def test_push_email_preferences_do_not_force_an_in_app_notice(inbox):
    from app.services.notification_service import NotificationService
    inbox.db.add(NotificationPreference(user_id=inbox.users[0].id, in_app=False, push=True, email=True))
    await inbox.db.flush()
    channels = await NotificationService.resolve_channels(inbox.db, inbox.users[0].id, "OTHER")
    assert channels.model_dump() == {"in_app": False, "push": True, "email": True}
    assert await emit(inbox, notification_type="OTHER") is None


async def test_duplicate_returns_same_record_even_after_disable_or_logical_delete(inbox):
    inbox.db.autoflush = False  # Match the production session factory.
    event = uuid4()
    item = await emit(inbox, event_id=event)
    inbox.db.add(NotificationPreference(user_id=inbox.users[0].id, in_app=False))
    await inbox.db.flush()
    assert (await emit(inbox, event_id=event)).id == item.id
    item.deleted_at = datetime.now(timezone.utc)
    deleted = await emit(inbox, event_id=event)
    assert deleted.id == item.id and deleted.deleted_at is not None
    assert await inbox.db.scalar(text("SELECT count(*) FROM notifications WHERE user_id=:id"), {"id": inbox.users[0].id}) == 1


async def test_pending_preference_change_is_respected_within_callers_transaction(inbox):
    inbox.db.autoflush = False
    inbox.db.add(NotificationPreference(user_id=inbox.users[0].id, in_app=False))
    assert await emit(inbox) is None
    assert await inbox.db.scalar(text("SELECT count(*) FROM notifications WHERE user_id=:id"), {"id": inbox.users[0].id}) == 0


async def test_same_event_is_independent_per_recipient(inbox):
    event = uuid4()
    a = await emit(inbox, event_id=event)
    b = await emit(inbox, event_id=event, user_id=inbox.users[1].id)
    assert a.id != b.id


@pytest.mark.parametrize("changes", [{"title": "Changed"}, {"message": "Changed"}, {"notification_type": "OTHER"}])
async def test_conflicting_event_content_is_not_overwritten(inbox, changes):
    event = uuid4()
    item = await emit(inbox, event_id=event)
    with pytest.raises(SkillMatchException) as failure:
        await emit(inbox, event_id=event, **changes)
    assert failure.value.statuscode == 409
    await inbox.db.refresh(item)
    assert item.title == "Title" and item.message == "Message" and item.type == "MATCH_RECEIVED"


@pytest.mark.parametrize("state", ["missing", "inactive", "locked"])
async def test_noneligible_recipient_never_gets_an_emission(inbox, state):
    user = inbox.users[0]
    if state == "inactive":
        user.is_active = False
    elif state == "locked":
        user.is_locked = True
    await inbox.db.flush()
    with pytest.raises(SkillMatchException):
        await emit(inbox, user_id=uuid4() if state == "missing" else user.id)
    assert await inbox.db.scalar(text("SELECT count(*) FROM notifications WHERE user_id=:id"), {"id": user.id}) == 0


async def test_invalid_payload_does_not_write_or_commit(inbox):
    with pytest.raises(ValidationError):
        await emit(inbox, title="\t ")
    assert await inbox.db.scalar(text("SELECT count(*) FROM notifications WHERE user_id=:id"), {"id": inbox.users[0].id}) == 0


async def test_caller_rollback_discards_notice_and_service_does_not_commit(persistence):
    from app.services.notification_service import NotificationService
    connection, _, users, _ = persistence
    async with AsyncSession(bind=connection, expire_on_commit=False) as db:
        item = await NotificationService.emit_in_app(db, user_id=users[0], event_id=uuid4(), notification_type="OTHER", title="Title", message="Message")
        identifier = item.id
        await db.rollback()
    assert await connection.scalar(select(Notification.id).where(Notification.id == identifier)) is None


async def test_concurrent_emissions_return_one_identity(persistence):
    from app.services.notification_service import NotificationService
    connection, schema, users, _ = persistence
    await connection.commit()
    from app.core.config import settings
    engine = create_async_engine(settings.async_database_url, connect_args={"server_settings": {"search_path": schema}})
    event = uuid4()
    try:
        async def write():
            async with AsyncSession(engine, expire_on_commit=False) as db:
                item = await NotificationService.emit_in_app(db, user_id=users[0], event_id=event, notification_type="OTHER", title="Title", message="Message")
                await db.commit()
                return item.id
        outcomes = await asyncio.gather(write(), write())
        assert outcomes[0] == outcomes[1]
        assert await connection.scalar(text("SELECT count(*) FROM notifications")) == 1
    finally:
        await engine.dispose()
