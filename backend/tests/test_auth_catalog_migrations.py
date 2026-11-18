"""Run actual Alembic upgrades and rollback on task-owned PostgreSQL schemas."""
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import insert, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.catalog_names import catalog_name_key
from app.core.config import settings
from app.models.user import User


@pytest.mark.asyncio
@pytest.mark.parametrize("duplicates", [False, True])
async def test_migrations_preserve_members_and_catalog_or_reject_conflicts_atomically(duplicates):
    engine = create_async_engine(settings.async_database_url)
    async with engine.connect() as connection:
        outer = await connection.begin()
        try:
            schema = f"test_hu_migrations_{uuid.uuid4().hex}"
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            await connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
            config.set_main_option("script_location", str(Path(__file__).parents[1] / "alembic"))
            def upgrade(sync_connection, target):
                config.attributes["connection"] = sync_connection
                command.upgrade(config, target)
            await connection.run_sync(upgrade, "b34c56d7e892")
            member_id, admin_id, category_id, skill_id = [uuid.uuid4() for _ in range(4)]
            await connection.execute(insert(User), [
                {"id": member_id, "email": "member@example.com", "full_name": "Member", "role": "MEMBER", "is_active": True, "is_locked": False},
                {"id": admin_id, "email": "admin@example.com", "full_name": "Admin", "role": "ADMIN", "is_active": True, "is_locked": False},
            ])
            await connection.execute(text("INSERT INTO categories (id,name,slug,is_active,created_at,updated_at) VALUES (:id,'Música','musica',true,now(),now())"), {"id": category_id})
            await connection.execute(text("INSERT INTO skills (id,category_id,name,slug,min_approval_threshold,is_ready_to_publish,is_active,created_at,updated_at) VALUES (:id,:cat,'Guitarra clásica','guitarra-clasica',80,false,true,now(),now())"), {"id": skill_id, "cat": category_id})
            if duplicates:
                await connection.execute(text("INSERT INTO skills (id,category_id,name,slug,min_approval_threshold,is_ready_to_publish,is_active,created_at,updated_at) VALUES (:id,:cat,'GUITARRA CLASICA','guitarra-clasica-2',80,false,true,now(),now())"), {"id": uuid.uuid4(), "cat": category_id})
                with pytest.raises(RuntimeError, match="Duplicate normalized catalog names"):
                    async with connection.begin_nested():
                        await connection.run_sync(upgrade, "head")
                assert (await connection.execute(text("SELECT version_num FROM alembic_version"))).scalar_one() == "b34c56d7e892"
                assert (await connection.execute(text("SELECT count(*) FROM skills"))).scalar_one() == 2
                assert (await connection.execute(text("SELECT count(*) FROM users"))).scalar_one() == 2
            else:
                await connection.run_sync(upgrade, "head")
                assert (await connection.execute(text("SELECT user_id,balance FROM wallets"))).all() == [(member_id, 0)]
                assert (await connection.execute(text("SELECT id,name,parent_id,normalized_name FROM categories"))).one() == (category_id, "Música", None, catalog_name_key("Música"))
                assert (await connection.execute(text("SELECT id,name,normalized_name FROM skills"))).one() == (skill_id, "Guitarra clásica", catalog_name_key("GUITARRA CLASICA"))
                assert (await connection.execute(text("SELECT count(*) FROM revoked_tokens"))).scalar_one() == 0
                assert (await connection.execute(text("SELECT version_num FROM alembic_version"))).scalar_one() == "f74e31b8a954"
        finally:
            await outer.rollback()
    await engine.dispose()
