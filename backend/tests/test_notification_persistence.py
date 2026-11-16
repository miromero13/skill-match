"""HU-25 persistence contract in isolated PostgreSQL schemas.

Every downgrade is restricted to hu25_persist_<uuid>; public is never downgraded.
"""
import asyncio
from datetime import datetime, timezone
from pathlib import Path
import re
from uuid import uuid4

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
import pytest
from sqlalchemy import inspect, MetaData, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.models import Base, User

PARENT = "b18a0c1d2e3f"
REVISION = "c25a1b2c3d4e"
pytestmark = pytest.mark.hu25


def signature(connection, schema):
    inspector = inspect(connection)
    return {name: (
        [(col["name"], str(col["type"]), col["nullable"], col.get("default")) for col in inspector.get_columns(name, schema=schema)],
        inspector.get_pk_constraint(name, schema=schema),
        inspector.get_foreign_keys(name, schema=schema),
        inspector.get_unique_constraints(name, schema=schema),
        inspector.get_check_constraints(name, schema=schema),
        inspector.get_indexes(name, schema=schema),
    ) for name in inspector.get_table_names(schema=schema)}


async def migrate(connection, schema, revision, downgrade=False):
    assert re.fullmatch(r"hu25_persist_[0-9a-f]{32}", schema)
    assert await connection.scalar(text("SELECT current_schema()")) == schema
    await connection.commit()

    def run(sync_connection):
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        config.attributes["connection"] = sync_connection
        (command.downgrade if downgrade else command.upgrade)(config, revision)
    await connection.run_sync(run)


@pytest.fixture
async def persistence():
    engine = create_async_engine(settings.async_database_url, pool_pre_ping=True)
    assert settings.ENVIRONMENT == "development"
    assert engine.url.host in {"localhost", "127.0.0.1", "::1"}
    schema = "hu25_persist_" + uuid4().hex
    try:
        async with engine.connect() as connection:
            before = await connection.run_sync(lambda c: signature(c, "public"))
            await connection.commit()
            created = False
            try:
                await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
                await connection.commit()
                created = True
                await connection.execute(text(f'SET search_path TO "{schema}"'))
                await connection.commit()
                await migrate(connection, schema, PARENT)
                async with AsyncSession(bind=connection, expire_on_commit=False) as db:
                    users = [User(id=uuid4(), email=f"hu25-persistence-{i}@example.invalid", full_name="HU25", role="MEMBER") for i in range(2)]
                    db.add_all(users)
                    await db.commit()
                previous = await connection.run_sync(lambda c: signature(c, schema))
                await migrate(connection, schema, REVISION)
                yield connection, schema, [u.id for u in users], previous
            finally:
                await connection.rollback()
                await connection.execute(text("SET search_path TO public"))
                await connection.commit()
                if created:
                    assert re.fullmatch(r"hu25_persist_[0-9a-f]{32}", schema)
                    await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
                    await connection.commit()
                assert await connection.run_sync(lambda c: signature(c, "public")) == before
                assert await connection.scalar(text("SELECT count(*) FROM pg_namespace WHERE nspname=:name"), {"name": schema}) == 0
    finally:
        await engine.dispose()


def notification_values(owner_id, **changes):
    return {"id": uuid4(), "event_id": uuid4(), "user_id": owner_id, "type": "MATCH_RECEIVED",
            "title": "Title", "message": "Message", **changes}


def preference_values(owner_id, **changes):
    now = datetime.now(timezone.utc)
    return {"user_id": owner_id, "created_at": now, "updated_at": now, **changes}


def test_models_registered_and_categories_are_derived():
    from app.models.notification import Notification, NotificationCategory, NotificationType
    from app.models.notification_preference import NotificationPreference
    assert Base.metadata.tables["notifications"] is Notification.__table__
    assert Base.metadata.tables["notification_preferences"] is NotificationPreference.__table__
    assert "category" not in Notification.__table__.c
    expected = {"MATCH_RECEIVED": "INTERCHANGES", "MATCH_CONFIRMED": "INTERCHANGES",
                "SESSION_PROPOSED": "INTERCHANGES", "POINTS_RECEIVED": "POINTS", "OTHER": "GENERAL"}
    assert {kind.value for kind in NotificationType} == set(expected)
    assert {kind.value for kind in NotificationCategory} == set(expected.values())
    for kind, category in expected.items():
        assert Notification(type=kind).category == category


async def test_upgrade_metadata_and_roundtrip_preserve_existing_tables(persistence):
    connection, schema, _, previous = persistence
    after = await connection.run_sync(lambda c: signature(c, schema))
    assert all(after[name] == value for name, value in previous.items())
    assert set(after) - set(previous) == {"notifications", "notification_preferences"}
    assert await connection.scalar(text("SELECT count(*) FROM users")) == 2
    assert await connection.scalar(text("SELECT version_num FROM alembic_version")) == REVISION

    def compare(sync_connection):
        metadata = MetaData()
        for table in Base.metadata.tables.values():
            table.to_metadata(metadata)
        names = {"notifications", "notification_preferences"}
        context = MigrationContext.configure(sync_connection, opts={
            "compare_server_default": True,
            "include_object": lambda obj, name, kind, reflected, other:
                name in names if kind == "table" else obj.table.name in names,
        })
        assert compare_metadata(context, metadata) == []
    await connection.run_sync(compare)
    await migrate(connection, schema, PARENT, downgrade=True)
    assert await connection.run_sync(lambda c: signature(c, schema)) == previous
    assert await connection.scalar(text("SELECT count(*) FROM users")) == 2
    await migrate(connection, schema, REVISION)
    assert await connection.scalar(text("SELECT count(*) FROM notifications")) == 0


async def test_indexes_are_partial_and_foreign_keys_cascade(persistence):
    connection, schema, _, _ = persistence

    def verify(sync_connection):
        inspector = inspect(sync_connection)
        indexes = {idx["name"]: idx for idx in inspector.get_indexes("notifications", schema=schema)}
        visible = indexes["ix_notifications_user_visible_order"]
        assert visible["column_names"] == ["user_id", "created_at", "id"]
        assert "deleted_at IS NULL" in str(visible["dialect_options"]["postgresql_where"])
        assert visible["column_sorting"]["created_at"] == ("desc",)
        unread = indexes["ix_notifications_user_unread"]
        assert "read_at IS NULL" in str(unread["dialect_options"]["postgresql_where"])
        assert "deleted_at IS NULL" in str(unread["dialect_options"]["postgresql_where"])
        for name in ["notifications", "notification_preferences"]:
            assert inspector.get_foreign_keys(name, schema=schema)[0]["options"]["ondelete"] == "CASCADE"
    await connection.run_sync(verify)


async def test_orm_defaults_timestamps_and_read_state(persistence):
    from app.models.notification import Notification
    from app.models.notification_preference import NotificationPreference
    connection, _, users, _ = persistence
    async with AsyncSession(bind=connection, expire_on_commit=False) as db:
        item = Notification(user_id=users[0], event_id=uuid4(), type="OTHER", title="Title", message="Message")
        prefs = NotificationPreference(user_id=users[0])
        db.add_all([item, prefs])
        await db.commit()
        assert item.id and item.created_at.utcoffset() is not None
        assert item.read_at is item.deleted_at is None
        assert prefs.revision == 1
        assert (prefs.in_app, prefs.push, prefs.email) == (True, False, False)
        assert prefs.interchanges and prefs.points and prefs.general
        assert prefs.created_at.utcoffset() is not None
        initial_time = prefs.updated_at
        prefs.push = True
        await db.commit()
        assert prefs.updated_at > initial_time
        db.expunge_all()
        stored = await db.get(Notification, item.id)
        assert stored.category == "GENERAL" and stored.read_at is None


@pytest.mark.parametrize("changes", [
    {"type": "INVALID"}, {"type": None}, {"user_id": uuid4()}, {"event_id": None},
    {"title": " "}, {"title": "x" * 151}, {"title": None},
    {"message": " "}, {"message": "x" * 2001}, {"message": None},
])
async def test_database_rejects_invalid_notification(persistence, changes):
    from app.models.notification import Notification
    connection, _, users, _ = persistence
    with pytest.raises(DBAPIError):
        async with connection.begin_nested():
            await connection.execute(Notification.__table__.insert().values(**notification_values(users[0], **changes)))


@pytest.mark.parametrize("changes", [
    {"revision": 0}, {"revision": -1}, {"revision": None}, {"user_id": uuid4()},
    {"in_app": None}, {"push": None}, {"email": None}, {"interchanges": None}, {"points": None}, {"general": None},
])
async def test_database_rejects_invalid_preferences(persistence, changes):
    from app.models.notification_preference import NotificationPreference
    connection, _, users, _ = persistence
    with pytest.raises(DBAPIError):
        async with connection.begin_nested():
            await connection.execute(NotificationPreference.__table__.insert().values(**preference_values(users[0], **changes)))


async def test_event_uniqueness_survives_logical_delete_and_is_per_user(persistence):
    from app.models.notification import Notification
    connection, _, users, _ = persistence
    event = uuid4()
    await connection.execute(Notification.__table__.insert().values(**notification_values(users[0], event_id=event, deleted_at=datetime.now(timezone.utc))))
    with pytest.raises(IntegrityError) as failure:
        async with connection.begin_nested():
            await connection.execute(Notification.__table__.insert().values(**notification_values(users[0], event_id=event)))
    assert "uq_notifications_user_event" in str(failure.value.orig)
    await connection.execute(Notification.__table__.insert().values(**notification_values(users[1], event_id=event)))
    assert await connection.scalar(text("SELECT count(*) FROM notifications")) == 2


async def test_preferences_unique_per_user_and_user_delete_cascades(persistence):
    from app.models.notification import Notification
    from app.models.notification_preference import NotificationPreference
    connection, _, users, _ = persistence
    for user in users:
        await connection.execute(Notification.__table__.insert().values(**notification_values(user)))
        await connection.execute(NotificationPreference.__table__.insert().values(**preference_values(user)))
    with pytest.raises(IntegrityError):
        async with connection.begin_nested():
            await connection.execute(NotificationPreference.__table__.insert().values(**preference_values(users[0])))
    await connection.execute(User.__table__.delete().where(User.id == users[0]))
    for name in ["notifications", "notification_preferences"]:
        assert await connection.scalar(text(f"SELECT count(*) FROM {name}")) == 1


async def test_exact_text_limits_and_timezone_roundtrip(persistence):
    from app.models.notification import Notification
    connection, _, users, _ = persistence
    now = datetime.now(timezone.utc)
    await connection.execute(Notification.__table__.insert().values(**notification_values(users[0], title="x"*150, message="x"*2000, read_at=now, deleted_at=now)))
    row = (await connection.execute(text("SELECT length(title), length(message), created_at, read_at, deleted_at FROM notifications"))).one()
    assert row[0:2] == (150, 2000)
    assert all(value.utcoffset() is not None for value in row[2:])


@pytest.mark.parametrize("table_name", ["notifications", "notification_preferences"])
async def test_concurrent_database_inserts_have_one_winner(persistence, table_name):
    from app.models.notification import Notification
    from app.models.notification_preference import NotificationPreference
    connection, schema, users, _ = persistence
    await connection.commit()
    engine = create_async_engine(settings.async_database_url, connect_args={"server_settings": {"search_path": schema}})
    event = uuid4()
    table = Notification.__table__ if table_name == "notifications" else NotificationPreference.__table__
    try:
        async def insert():
            values = notification_values(users[0], event_id=event) if table_name == "notifications" else preference_values(users[0])
            async with engine.begin() as writer:
                await writer.execute(table.insert().values(**values))
        outcomes = await asyncio.gather(insert(), insert(), return_exceptions=True)
        assert sum(result is None for result in outcomes) == 1
        assert sum(isinstance(result, IntegrityError) for result in outcomes) == 1
        assert await connection.scalar(text(f"SELECT count(*) FROM {table_name}")) == 1
    finally:
        await engine.dispose()
