"""Real PostgreSQL checks in disposable schemas; never downgrade public."""

import asyncio
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import MetaData, inspect, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.models import Base, Category, Skill, SkillEvidence, TeachingSkill, User

REVISION = "a16e0b7c9d42"
PARENT = "f69de0a4b8f0"
INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def public_signature(connection):
    inspector = inspect(connection)
    return {
        name: (
            [(col["name"], str(col["type"]), col["nullable"]) for col in inspector.get_columns(name, schema="public")],
            inspector.get_pk_constraint(name, schema="public"),
            inspector.get_foreign_keys(name, schema="public"),
            inspector.get_unique_constraints(name, schema="public"),
            inspector.get_check_constraints(name, schema="public"),
            inspector.get_indexes(name, schema="public"),
        ) for name in inspector.get_table_names(schema="public")
    }


async def migrate(connection, schema, revision, downgrade=False):
    # Check the actual target immediately before every migration command.
    assert re.fullmatch(r"hu16_test_[0-9a-f]{32}", schema)
    assert await connection.scalar(text("SELECT current_schema()")) == schema
    await connection.commit()

    def run(sync_connection):
        config = Config(str(INI))
        config.attributes["connection"] = sync_connection
        if downgrade:
            command.downgrade(config, revision)
        else:
            command.upgrade(config, revision)

    await connection.run_sync(run)


@pytest.fixture
async def migrated_schema():
    engine = create_async_engine(settings.async_database_url, pool_pre_ping=True)
    schema = "hu16_test_" + uuid4().hex
    try:
        async with engine.connect() as connection:
            before = await connection.run_sync(public_signature)
            await connection.commit()
            created = False
            try:
                await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
                await connection.commit()
                created = True
                await connection.execute(text(f'SET search_path TO "{schema}"'))
                await connection.commit()
                await migrate(connection, schema, PARENT)
                # Data predates the new revision, testing an actual HU-14 upgrade.
                now = datetime.now(timezone.utc)
                user_id = uuid4()
                cat_id = uuid4()
                skill_1_id = uuid4()
                skill_2_id = uuid4()
                offer_ids = [uuid4(), uuid4()]

                await connection.execute(
                    text("""
                        INSERT INTO users (id, email, full_name, role, is_active, is_locked, failed_login_attempts, created_at, updated_at)
                        VALUES (:id, :email, :full_name, :role, :is_active, :is_locked, :failed_login_attempts, :created_at, :updated_at)
                    """),
                    {
                        "id": user_id,
                        "email": "migration@example.invalid",
                        "full_name": "Migration",
                        "role": "MEMBER",
                        "is_active": True,
                        "is_locked": False,
                        "failed_login_attempts": 0,
                        "created_at": now,
                        "updated_at": now,
                    },
                )
                await connection.execute(
                    text("""
                        INSERT INTO categories (id, name, slug, description, is_active, created_at, updated_at)
                        VALUES (:id, :name, :slug, :description, :is_active, :created_at, :updated_at)
                    """),
                    {
                        "id": cat_id,
                        "name": "Migration",
                        "slug": "migration",
                        "description": None,
                        "is_active": True,
                        "created_at": now,
                        "updated_at": now,
                    },
                )
                await connection.execute(
                    text("""
                        INSERT INTO skills (id, category_id, name, slug, description, min_approval_threshold, is_ready_to_publish, is_active, created_at, updated_at)
                        VALUES (:id, :category_id, :name, :slug, :description, :min_approval_threshold, :is_ready_to_publish, :is_active, :created_at, :updated_at)
                    """),
                    {
                        "id": skill_1_id,
                        "category_id": cat_id,
                        "name": "Migration Skill 1",
                        "slug": "migration-skill-1",
                        "description": None,
                        "min_approval_threshold": 70.0,
                        "is_ready_to_publish": True,
                        "is_active": True,
                        "created_at": now,
                        "updated_at": now,
                    },
                )
                await connection.execute(
                    text("""
                        INSERT INTO skills (id, category_id, name, slug, description, min_approval_threshold, is_ready_to_publish, is_active, created_at, updated_at)
                        VALUES (:id, :category_id, :name, :slug, :description, :min_approval_threshold, :is_ready_to_publish, :is_active, :created_at, :updated_at)
                    """),
                    {
                        "id": skill_2_id,
                        "category_id": cat_id,
                        "name": "Migration Skill 2",
                        "slug": "migration-skill-2",
                        "description": None,
                        "min_approval_threshold": 70.0,
                        "is_ready_to_publish": True,
                        "is_active": True,
                        "created_at": now,
                        "updated_at": now,
                    },
                )
                for oid, sid in zip(offer_ids, [skill_1_id, skill_2_id]):
                    await connection.execute(
                        text("""
                            INSERT INTO user_teaching_skills (id, user_id, skill_id, declared_level, years_of_experience, description, accepts_points, hourly_points_rate, status, created_at, updated_at)
                            VALUES (:id, :user_id, :skill_id, :declared_level, :years_of_experience, :description, :accepts_points, :hourly_points_rate, :status, :created_at, :updated_at)
                        """),
                        {
                            "id": oid,
                            "user_id": user_id,
                            "skill_id": sid,
                            "declared_level": "BEGINNER",
                            "years_of_experience": 1,
                            "description": None,
                            "accepts_points": False,
                            "hourly_points_rate": None,
                            "status": "DECLARADA",
                            "created_at": now,
                            "updated_at": now,
                        },
                    )
                await connection.commit()
                await migrate(connection, schema, REVISION)
                yield connection, schema, offer_ids
            finally:
                await connection.rollback()
                await connection.execute(text("SET search_path TO public"))
                await connection.commit()
                if created:
                    assert re.fullmatch(r"hu16_test_[0-9a-f]{32}", schema)
                    await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
                    await connection.commit()
                after = await connection.run_sync(public_signature)
                assert after == before, "Disposable migration changed public schema"
                remaining = await connection.scalar(
                    text("SELECT count(*) FROM pg_namespace WHERE nspname = :schema"), {"schema": schema},
                )
                assert remaining == 0
    finally:
        await engine.dispose()


def evidence_values(offer_id, **changes):
    now = datetime.now(timezone.utc)
    return {
        "id": uuid4(), "teaching_skill_id": offer_id, "title": "Project",
        "description": None, "url": "https://example.com/evidence", "evidence_type": "REPOSITORY",
        "created_at": now, "updated_at": now, **changes,
    }


async def test_upgrade_metadata_and_downgrade_preserve_hu14(migrated_schema):
    connection, schema, offers = migrated_schema
    assert await connection.scalar(text("SELECT version_num FROM alembic_version")) == REVISION
    assert await connection.scalar(text("SELECT count(*) FROM user_teaching_skills")) == 2

    def verify(sync_connection):
        inspector = inspect(sync_connection)
        columns = {col["name"]: col for col in inspector.get_columns("skill_evidences", schema=schema)}
        assert columns["url"]["type"].length == 2048
        assert columns["created_at"]["type"].timezone
        assert inspector.get_foreign_keys("skill_evidences", schema=schema)[0]["options"]["ondelete"] == "CASCADE"
        assert inspector.get_unique_constraints("skill_evidences", schema=schema)[0]["column_names"] == ["teaching_skill_id", "url"]
        assert "ix_skill_evidences_teaching_skill_id" in {
            index["name"] for index in inspector.get_indexes("skill_evidences", schema=schema)
        }
        # Compare only this feature; inherited HU-14 drift is deliberately excluded.
        metadata = MetaData()
        for table in Base.metadata.tables.values():
            table.to_metadata(metadata)
        context = MigrationContext.configure(sync_connection, opts={
            "include_object": lambda obj, name, kind, reflected, compare_to:
                (name == "skill_evidences" if kind == "table" else obj.table.name == "skill_evidences"),
        })
        assert compare_metadata(context, metadata) == []

    await connection.run_sync(verify)
    await migrate(connection, schema, PARENT, downgrade=True)
    assert await connection.scalar(text("SELECT to_regclass('skill_evidences')")) is None
    assert await connection.scalar(text("SELECT count(*) FROM user_teaching_skills")) == 2
    assert await connection.scalar(text("SELECT version_num FROM alembic_version")) == PARENT
    await migrate(connection, schema, REVISION)
    assert await connection.scalar(text("SELECT count(*) FROM skill_evidences")) == 0


@pytest.mark.parametrize("kind", ["REPOSITORY", "VIDEO", "CERTIFICATE", "OTHER"])
async def test_orm_defaults_and_timestamps_roundtrip(migrated_schema, kind):
    connection, _, offers = migrated_schema
    async with AsyncSession(bind=connection, expire_on_commit=False) as db:
        item = SkillEvidence(teaching_skill_id=offers[0], title="Evidence", url="https://example.com/", evidence_type=kind)
        db.add(item)
        await db.flush()
        assert item.id and item.created_at.utcoffset() is not None
        created_at, updated_at, item_id = item.created_at, item.updated_at, item.id
        await db.commit()
        item.title = "Updated"
        await db.commit()
        assert item.created_at == created_at and item.updated_at > updated_at
        db.expunge_all()
        saved = await db.get(SkillEvidence, item_id)
        assert saved.title == "Updated" and saved.evidence_type == kind


@pytest.mark.parametrize(
    ("changes", "constraint"),
    [
        ({"evidence_type": "UNKNOWN"}, "ck_skill_evidences_type"),
        ({"title": "   "}, "ck_skill_evidences_title"),
        ({"url": "javascript:alert(1)"}, "ck_skill_evidences_url_scheme"),
        ({"teaching_skill_id": uuid4()}, "fk_skill_evidences_teaching_skill_id"),
    ],
)
async def test_database_constraints_reject_invalid_values(migrated_schema, changes, constraint):
    connection, _, offers = migrated_schema
    with pytest.raises(IntegrityError) as failure:
        async with connection.begin_nested():
            await connection.execute(SkillEvidence.__table__.insert().values(**evidence_values(offers[0], **changes)))
    assert constraint in str(failure.value.orig)


@pytest.mark.parametrize("changes", [
    {"title": "x" * 151}, {"description": "x" * 2001},
    {"url": "https://example.com/" + "x" * 2048}, {"title": None}, {"url": None},
])
async def test_database_lengths_and_required_fields(migrated_schema, changes):
    connection, _, offers = migrated_schema
    with pytest.raises(DBAPIError):
        async with connection.begin_nested():
            await connection.execute(SkillEvidence.__table__.insert().values(**evidence_values(offers[0], **changes)))


async def test_unique_scope_and_cascade(migrated_schema):
    connection, _, offers = migrated_schema
    table = SkillEvidence.__table__
    await connection.execute(table.insert().values(**evidence_values(offers[0])))
    with pytest.raises(IntegrityError) as failure:
        async with connection.begin_nested():
            await connection.execute(table.insert().values(**evidence_values(offers[0])))
    assert "uq_skill_evidences_skill_url" in str(failure.value.orig)
    await connection.execute(table.insert().values(**evidence_values(offers[1])))
    await connection.execute(TeachingSkill.__table__.delete().where(TeachingSkill.id == offers[0]))
    assert len((await connection.execute(select(table.c.id))).all()) == 1
    await connection.execute(User.__table__.delete())
    assert (await connection.execute(select(table.c.id))).all() == []


async def test_concurrent_duplicate_inserts_have_one_winner(migrated_schema):
    connection, schema, offers = migrated_schema
    await connection.commit()
    engine = create_async_engine(
        settings.async_database_url,
        connect_args={"server_settings": {"search_path": schema}},
    )
    try:
        async def insert():
            async with engine.begin() as writer:
                await writer.execute(
                    SkillEvidence.__table__.insert().values(**evidence_values(offers[0])),
                )

        outcomes = await asyncio.gather(insert(), insert(), return_exceptions=True)
        assert sum(outcome is None for outcome in outcomes) == 1
        rejected = [outcome for outcome in outcomes if isinstance(outcome, IntegrityError)]
        assert len(rejected) == 1
        assert "uq_skill_evidences_skill_url" in str(rejected[0].orig)
        assert await connection.scalar(text("SELECT count(*) FROM skill_evidences")) == 1
    finally:
        await engine.dispose()


async def test_maximum_field_lengths_are_storable(migrated_schema):
    connection, _, offers = migrated_schema
    url = "https://example.com/" + "x" * (2048 - len("https://example.com/"))
    await connection.execute(SkillEvidence.__table__.insert().values(**evidence_values(
        offers[0], title="x" * 150, description="x" * 2000, url=url,
    )))
    assert await connection.scalar(text("SELECT length(url) FROM skill_evidences")) == 2048


@pytest.mark.hu16
async def test_concurrent_api_requests_return_created_and_conflict(migrated_schema):
    from datetime import timedelta

    from httpx import ASGITransport, AsyncClient
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.core.deps import get_current_user
    from app.core.security import create_access_token
    from app.db.session import get_db
    from app.main import create_application
    from app.models.user import UserRole

    connection, schema, offers = migrated_schema
    owner_id = await connection.scalar(select(TeachingSkill.user_id).where(TeachingSkill.id == offers[0]))
    await connection.commit()
    engine = create_async_engine(
        settings.async_database_url,
        connect_args={"server_settings": {"search_path": schema}},
    )
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    app = create_application()

    async def isolated_db():
        async with sessions() as db:
            try:
                yield db
                await db.commit()
            except Exception:
                await db.rollback()
                raise

    dummy_user = User(
        id=owner_id,
        email="migration@example.invalid",
        full_name="Migration",
        role=UserRole.MEMBER,
        is_active=True,
    )
    async def override_current_user():
        return dummy_user

    app.dependency_overrides[get_db] = isolated_db
    app.dependency_overrides[get_current_user] = override_current_user
    token = create_access_token(str(owner_id), "MEMBER", timedelta(minutes=5))
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            async def post(url):
                return await client.post(
                    f"/api/users/me/teaching-skills/{offers[0]}/evidences",
                    headers={"Authorization": "Bearer " + token},
                    json={"title": "Concurrent", "url": url, "evidence_type": "OTHER"},
                )

            responses = await asyncio.gather(post("https://EXAMPLE.COM"), post("https://example.com/"))
            assert sorted(response.status_code for response in responses) == [201, 409]
            conflict = next(response for response in responses if response.status_code == 409)
            assert conflict.json() == {
                "statuscode": 409, "message": "Ya registraste esta evidencia.", "data": None,
            }
            listed = await client.get(
                f"/api/users/me/teaching-skills/{offers[0]}/evidences",
                headers={"Authorization": "Bearer " + token},
            )
            assert listed.status_code == 200 and listed.json()["count"] == 1
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()
