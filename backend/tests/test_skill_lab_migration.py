"""Skill lab migration (S3/S5 storage) on a disposable PostgreSQL schema; `public` is never migrated here."""
import re
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings

REVISION = "e7a4c1d9b352"
PARENT = "dcb1bfb4bae8"
BACKEND = Path(__file__).resolve().parents[1]


def _config(sync_connection=None) -> Config:
    # No ini file on purpose: env.py would run logging.fileConfig() and disable the app loggers
    # that later tests assert on with caplog.
    config = Config()
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    config.set_main_option("path_separator", "os")
    if sync_connection is not None:
        config.attributes["connection"] = sync_connection
    return config


async def _migrate(connection, schema: str, target: str, downgrade: bool = False) -> None:
    # Re-check the target schema right before every Alembic command.
    assert re.fullmatch(r"test_skill_lab_mig_[0-9a-f]{32}", schema)
    assert await connection.scalar(text("SELECT current_schema()")) == schema

    def run(sync_connection):
        config = _config(sync_connection)
        (command.downgrade if downgrade else command.upgrade)(config, target)

    await connection.run_sync(run)


def _columns(sync_connection, table: str, schema: str) -> dict[str, dict]:
    return {col["name"]: col for col in inspect(sync_connection).get_columns(table, schema=schema)}


def _foreign_keys(sync_connection, table: str, schema: str) -> dict[str, dict]:
    return {
        fk["constrained_columns"][0]: fk
        for fk in inspect(sync_connection).get_foreign_keys(table, schema=schema)
    }


def _indexes(sync_connection, table: str, schema: str) -> set[str]:
    return {index["name"] for index in inspect(sync_connection).get_indexes(table, schema=schema)}


def test_revision_is_the_single_head_on_top_of_the_merged_dev_head():
    script = ScriptDirectory.from_config(_config())
    assert script.get_heads() == [REVISION]
    assert script.get_revision(REVISION).down_revision == PARENT


@pytest.mark.asyncio
async def test_upgrade_downgrade_upgrade_is_additive_and_preserves_existing_rows():
    engine = create_async_engine(settings.async_database_url)
    try:
        async with engine.connect() as connection:
            outer = await connection.begin()
            try:
                schema = f"test_skill_lab_mig_{uuid.uuid4().hex}"
                await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
                await connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                await _migrate(connection, schema, PARENT)

                legacy_sample, legacy_model = uuid.uuid4(), uuid.uuid4()
                await connection.execute(text(
                    "INSERT INTO dataset_samples (id, discipline, challenge, hardware_info, signed_consent, file_format,"
                    " file_size_bytes, file_hash_sha256, storage_path, level_label, created_at, updated_at)"
                    " VALUES (:id, 'futbol', 'juggling', 'cam', true, 'mp4', 10, :hash, 'datasets/futbol/x.mp4',"
                    " 'Intermedio', now(), now())"
                ), {"id": legacy_sample, "hash": "a" * 64})
                await connection.execute(text(
                    "INSERT INTO model_versions (id, nombre, version, ruta_onnx, metricas, activa, created_at, updated_at)"
                    " VALUES (:id, 'level_classifier', 'v1', 'models/x.onnx', '{}', true, now(), now())"
                ), {"id": legacy_model})

                await _migrate(connection, schema, REVISION)
                columns = await connection.run_sync(_columns, "dataset_samples", schema)
                for name in ("skill_id", "skill_level_id", "criterion_key", "analysis"):
                    assert columns[name]["nullable"] is True
                assert columns["criterion_key"]["type"].length == 64
                assert columns["sample_role"]["nullable"] is False
                assert columns["sample_role"]["type"].length == 20
                assert "TRAINING" in str(columns["sample_role"]["default"])
                fks = await connection.run_sync(_foreign_keys, "dataset_samples", schema)
                assert fks["skill_id"]["referred_table"] == "skills"
                assert fks["skill_id"]["options"]["ondelete"] == "SET NULL"
                assert fks["skill_level_id"]["referred_table"] == "skill_levels"
                assert fks["skill_level_id"]["options"]["ondelete"] == "SET NULL"
                assert {"ix_dataset_samples_skill_id", "ix_dataset_samples_skill_level_id"} <= await connection.run_sync(
                    _indexes, "dataset_samples", schema
                )
                model_columns = await connection.run_sync(_columns, "model_versions", schema)
                assert model_columns["skill_id"]["nullable"] is True
                model_fks = await connection.run_sync(_foreign_keys, "model_versions", schema)
                assert model_fks["skill_id"]["referred_table"] == "skills"
                assert model_fks["skill_id"]["options"]["ondelete"] == "CASCADE"
                assert "ix_model_versions_skill_id" in await connection.run_sync(_indexes, "model_versions", schema)

                # Existing rows are untouched; the new role column reads its server default.
                row = (await connection.execute(text(
                    "SELECT discipline, level_label, skill_id, skill_level_id, criterion_key, sample_role, analysis"
                    " FROM dataset_samples WHERE id = :id"
                ), {"id": legacy_sample})).one()
                assert tuple(row) == ("futbol", "Intermedio", None, None, None, "TRAINING", None)
                assert (await connection.execute(text(
                    "SELECT nombre, activa, skill_id FROM model_versions WHERE id = :id"
                ), {"id": legacy_model})).one() == ("level_classifier", True, None)

                # Linkage semantics: level/skill removal unlinks samples; skill removal drops its models.
                category, skill, level = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
                await connection.execute(text(
                    "INSERT INTO categories (id, name, slug, normalized_name, is_active, created_at, updated_at)"
                    " VALUES (:id, 'Deportes', 'deportes', 'deportes', true, now(), now())"
                ), {"id": category})
                await connection.execute(text(
                    "INSERT INTO skills (id, category_id, name, slug, normalized_name, min_approval_threshold,"
                    " is_ready_to_publish, is_active, created_at, updated_at)"
                    " VALUES (:id, :cat, 'Dominadas', 'dominadas', 'dominadas', 80, false, false, now(), now())"
                ), {"id": skill, "cat": category})
                await connection.execute(text(
                    "INSERT INTO skill_levels (id, skill_id, level_number, name, created_at, updated_at)"
                    " VALUES (:id, :skill, 1, 'Básico', now(), now())"
                ), {"id": level, "skill": skill})
                linked = uuid.uuid4()
                await connection.execute(text(
                    "INSERT INTO dataset_samples (id, discipline, challenge, hardware_info, signed_consent, file_format,"
                    " file_size_bytes, file_hash_sha256, storage_path, skill_id, skill_level_id, criterion_key,"
                    " sample_role, created_at, updated_at) VALUES (:id, 'deportes', 'Dominadas', 'skill-lab-upload',"
                    " true, 'webm', 10, :hash, 'datasets/skill-lab/deportes/y.webm', :skill, :level, 'c1', 'REFERENCE',"
                    " now(), now())"
                ), {"id": linked, "hash": "b" * 64, "skill": skill, "level": level})
                validator_ids = [uuid.uuid4(), uuid.uuid4()]
                for index, model_id in enumerate(validator_ids):
                    await connection.execute(text(
                        "INSERT INTO model_versions (id, nombre, version, ruta_onnx, metricas, activa, skill_id,"
                        " created_at, updated_at) VALUES (:id, 'skill_validator', :v, '', '{}', :active, :skill, now(), now())"
                    ), {"id": model_id, "v": f"v{index + 1}", "active": index == 0, "skill": skill})
                # Only one active validator per skill; the football classifier never collides with it.
                with pytest.raises(IntegrityError):
                    async with connection.begin_nested():
                        await connection.execute(text(
                            "INSERT INTO model_versions (id, nombre, version, ruta_onnx, metricas, activa, skill_id,"
                            " created_at, updated_at) VALUES (:id, 'skill_validator', 'v3', '', '{}', true, :skill, now(), now())"
                        ), {"id": uuid.uuid4(), "skill": skill})
                await connection.execute(text("DELETE FROM skill_levels WHERE id = :id"), {"id": level})
                assert (await connection.execute(text(
                    "SELECT skill_id, skill_level_id FROM dataset_samples WHERE id = :id"
                ), {"id": linked})).one() == (skill, None)
                await connection.execute(text("DELETE FROM skills WHERE id = :id"), {"id": skill})
                assert (await connection.execute(text(
                    "SELECT skill_id FROM dataset_samples WHERE id = :id"
                ), {"id": linked})).scalar_one() is None
                assert (await connection.execute(text(
                    "SELECT count(*) FROM model_versions WHERE nombre = 'skill_validator'"
                ))).scalar_one() == 0
                await connection.execute(text("DELETE FROM dataset_samples WHERE id = :id"), {"id": linked})

                await _migrate(connection, schema, PARENT, downgrade=True)
                columns = await connection.run_sync(_columns, "dataset_samples", schema)
                assert not {"skill_id", "skill_level_id", "criterion_key", "sample_role", "analysis"} & set(columns)
                assert "skill_id" not in await connection.run_sync(_columns, "model_versions", schema)
                assert (await connection.execute(text(
                    "SELECT discipline, level_label FROM dataset_samples WHERE id = :id"
                ), {"id": legacy_sample})).one() == ("futbol", "Intermedio")
                assert (await connection.execute(text("SELECT count(*) FROM model_versions"))).scalar_one() == 1
                assert (await connection.execute(text("SELECT version_num FROM alembic_version"))).scalar_one() == PARENT

                await _migrate(connection, schema, REVISION)
                assert (await connection.execute(text("SELECT version_num FROM alembic_version"))).scalar_one() == REVISION
                assert (await connection.execute(text(
                    "SELECT sample_role FROM dataset_samples WHERE id = :id"
                ), {"id": legacy_sample})).scalar_one() == "TRAINING"
            finally:
                await outer.rollback()
    finally:
        await engine.dispose()
