"""Skill lab admin API (S2, S3, S4, S7) through HTTP + APIResponse, in an uncommitted isolated schema.

Every row lives in a throwaway PostgreSQL schema that is rolled back, and every stored file is
written under the pytest tmp path (cwd is switched there and S3 replication is disabled).
"""
import hashlib
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token
from app.football.models import ModelVersion
from app.football.services.storage import garage_s3_storage
from app.main import app
from app.models.catalog import Category, Rubric, Skill, SkillLevel
from app.models.user import User
from app.services import skill_lab_service
from auth_catalog_fixtures import isolated_db  # noqa: F401

LAB = "/api/admin/skill-lab"
NOT_FOUND = {"statuscode": 404, "message": "Recurso no encontrado", "data": None}


@pytest.fixture
async def lab(isolated_db, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(garage_s3_storage, "access_key_id", None)
    users = [User(id=uuid.uuid4(), email=f"lab-{role.lower()}@example.com", full_name=role, role=role,
                  is_active=True, is_locked=False) for role in ("ADMIN", "MEMBER")]
    isolated_db.add_all(users)
    await isolated_db.commit()
    headers = [{"Authorization": f"Bearer {create_access_token(str(user.id), user.role)}"} for user in users]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        yield SimpleNamespace(client=client, admin=headers[0], member=headers[1], db=isolated_db,
                              storage=tmp_path / "storage", catalog={})


async def _create_skill(ctx, **overrides):
    if not ctx.catalog:
        category = await ctx.client.post("/api/admin/catalog/categories", headers=ctx.admin, json={"name": "Deportes"})
        challenge = await ctx.client.post("/api/admin/catalog/challenge-types", headers=ctx.admin, json={
            "name": "Video en vivo", "code": "LIVE_VIDEO", "evaluation_modality": "VIDEO",
        })
        ctx.catalog.update(category_id=category.json()["data"]["id"], challenge_type_id=challenge.json()["data"]["id"])
    payload = {
        "category_id": ctx.catalog["category_id"],
        "challenge_type_id": ctx.catalog["challenge_type_id"],
        "name": "Dominadas",
        "min_approval_threshold": 75,
        "levels": [
            {"level_number": 1, "name": "Básico", "rubric": {"min_score": 60, "criteria": [
                {"key": "postura", "name": "Postura", "weight": 60, "description": "Replica la postura"},
                {"key": "toques", "name": "Toques", "weight": 40, "description": "Toques seguidos",
                 "metric_type": "BALL_TOUCH_STREAK", "target": 20},
            ]}},
            {"level_number": 2, "name": "Avanzado", "rubric": {"min_score": 80, "criteria": []}},
        ],
        **overrides,
    }
    response = await ctx.client.post("/api/admin/catalog/skills", headers=ctx.admin, json=payload)
    assert response.status_code == 201, response.text
    skill = response.json()["data"]
    # The catalog contract does not expose level ids; the lab config is where the admin UI reads them.
    config = await ctx.client.get(f"{LAB}/skills/{skill['id']}", headers=ctx.admin)
    for level, lab_level in zip(skill["levels"], config.json()["data"]["levels"], strict=True):
        assert level["level_number"] == lab_level["level_number"]
        level["id"] = lab_level["id"]
    return skill, payload


async def _config(ctx, skill_id):
    response = await ctx.client.get(f"{LAB}/skills/{skill_id}", headers=ctx.admin)
    assert response.status_code == 200, response.text
    return response.json()


async def _upload(ctx, skill_id, level_id, *, role="TRAINING", criterion_key=None, filename="clip.mp4",
                  content=b"fake-video-bytes", consent="true", participant_id=None, headers=None):
    data = {"skill_level_id": str(level_id), "sample_role": role, "signed_consent": consent}
    if criterion_key is not None:
        data["criterion_key"] = criterion_key
    if participant_id is not None:
        data["participant_id"] = participant_id
    return await ctx.client.post(
        f"{LAB}/skills/{skill_id}/samples",
        headers=ctx.admin if headers is None else headers,
        data=data,
        files={"file": (filename, content, "video/mp4")},
    )


async def _samples(ctx, skill_id):
    response = await ctx.client.get(f"{LAB}/skills/{skill_id}/samples", headers=ctx.admin)
    assert response.status_code == 200, response.text
    return response.json()


def _stored_files(ctx) -> list[Path]:
    root = ctx.storage / "datasets" / "skill-lab"
    return sorted(path for path in root.rglob("*") if path.is_file()) if root.exists() else []


def _assert_sample_shape(sample):
    assert set(sample) == {"id", "skill_id", "skill_level_id", "criterion_key", "sample_role", "file_format",
                           "file_size_bytes", "participant_id", "analysis_ready", "analysis_notes", "created_at"}


# ---------------------------------------------------------------- S7: admin only


@pytest.mark.asyncio
@pytest.mark.parametrize("who", ["anonymous", "member"])
async def test_every_lab_endpoint_is_hidden_from_members_and_anonymous(lab, who):
    skill, _ = await _create_skill(lab)
    level_id = skill["levels"][0]["id"]
    uploaded = await _upload(lab, skill["id"], level_id)
    assert uploaded.status_code == 201
    sample_id = uploaded.json()["data"]["id"]
    files_before = _stored_files(lab)
    headers = {} if who == "anonymous" else lab.member
    calls = [
        lab.client.get(f"{LAB}/metric-types", headers=headers),
        lab.client.get(f"{LAB}/skills/{skill['id']}", headers=headers),
        lab.client.get(f"{LAB}/skills/{skill['id']}/samples", headers=headers),
        lab.client.get(f"{LAB}/skills/{skill['id']}/models", headers=headers),
        lab.client.delete(f"{LAB}/samples/{sample_id}", headers=headers),
        _upload(lab, skill["id"], level_id, headers=headers),
    ]
    for call in calls:
        response = await call
        assert response.status_code == 404
        assert response.json() == NOT_FOUND
    listed = await _samples(lab, skill["id"])
    assert listed["count"] == 1 and listed["data"][0]["id"] == sample_id
    assert _stored_files(lab) == files_before


# ---------------------------------------------------------------- metric types / config (S1, S2)


@pytest.mark.asyncio
async def test_metric_types_lists_the_two_supported_codes(lab):
    response = await lab.client.get(f"{LAB}/metric-types", headers=lab.admin)
    assert response.status_code == 200
    body = response.json()
    assert body["statuscode"] == 200 and body["count"] == 2
    by_code = {item["code"]: item for item in body["data"]}
    assert set(by_code) == {"REFERENCE_REPLICATION", "BALL_TOUCH_STREAK"}
    assert by_code["REFERENCE_REPLICATION"]["requires_reference"] is True
    assert by_code["REFERENCE_REPLICATION"]["requires_target"] is False
    assert by_code["BALL_TOUCH_STREAK"]["requires_target"] is True
    assert by_code["BALL_TOUCH_STREAK"]["requires_reference"] is False
    for item in body["data"]:
        assert set(item) == {"code", "name", "description", "requires_target", "requires_reference"}
        assert item["name"] and item["description"]


@pytest.mark.asyncio
async def test_lab_config_reads_every_catalog_parameter_and_reports_missing_references(lab):
    skill, payload = await _create_skill(lab)
    body = await _config(lab, skill["id"])
    assert body["statuscode"] == 200
    assert body["message"] == "Configuración del laboratorio recuperada exitosamente."
    data = body["data"]
    assert set(data) == {"skill", "levels", "active_model", "readiness"}
    assert data["skill"] == {
        "id": skill["id"], "name": "Dominadas",
        "category": {"id": payload["category_id"], "name": "Deportes"},
        "challenge_type": {"id": payload["challenge_type_id"], "name": "Video en vivo", "code": "LIVE_VIDEO",
                           "evaluation_modality": "VIDEO"},
        "min_approval_threshold": 75.0,
    }
    first, second = data["levels"]
    assert {key: first[key] for key in ("id", "level_number", "name", "min_score", "weights_total",
                                        "training_samples", "reference")} == {
        "id": skill["levels"][0]["id"], "level_number": 1, "name": "Básico", "min_score": 60.0,
        "weights_total": 100.0, "training_samples": 0, "reference": None,
    }
    assert first["criteria"] == [
        {"key": "postura", "name": "Postura", "weight": 60.0, "description": "Replica la postura",
         "metric_type": "REFERENCE_REPLICATION", "target": None, "training_samples": 0, "has_reference": False},
        {"key": "toques", "name": "Toques", "weight": 40.0, "description": "Toques seguidos",
         "metric_type": "BALL_TOUCH_STREAK", "target": 20.0, "training_samples": 0, "has_reference": False},
    ]
    assert second["criteria"] == [] and second["min_score"] == 80.0 and second["weights_total"] == 0
    assert data["active_model"] is None
    assert data["readiness"] == {
        "ready_to_validate": False,
        "issues": ["El nivel «Básico» no tiene video de referencia.",
                   "El nivel «Avanzado» no tiene video de referencia."],
    }


@pytest.mark.asyncio
async def test_lab_config_reports_weights_and_missing_levels_without_repairing(lab):
    category = Category(name="Música", slug="musica")
    legacy = Skill(category=category, name="Guitarra", slug="guitarra")
    legacy.levels = [SkillLevel(level_number=1, name="Inicial", rubric=Rubric(min_score=70, criteria=[
        {"name": "Ritmo", "weight": 30, "description": "Legado"},
        {"name": "Afinación", "weight": 30, "description": "Legado"},
    ]))]
    empty = Skill(category=category, name="Piano", slug="piano")
    lab.db.add_all([legacy, empty])
    await lab.db.commit()

    legacy_data = (await _config(lab, legacy.id))["data"]
    assert legacy_data["skill"]["challenge_type"] is None
    level = legacy_data["levels"][0]
    assert level["weights_total"] == 60.0
    assert all(c["key"] and c["metric_type"] == "REFERENCE_REPLICATION" for c in level["criteria"])
    catalog_keys = [c["key"] for c in (await lab.client.get(
        f"/api/admin/catalog/skills/{legacy.id}", headers=lab.admin)).json()["data"]["levels"][0]["rubric"]["criteria"]]
    assert [c["key"] for c in level["criteria"]] == catalog_keys
    assert legacy_data["readiness"] == {"ready_to_validate": False, "issues": [
        "Los porcentajes de los criterios del nivel «Inicial» deben sumar 100% (actual: 60%).",
        "El nivel «Inicial» no tiene video de referencia.",
    ]}

    empty_data = (await _config(lab, empty.id))["data"]
    assert empty_data["levels"] == []
    assert empty_data["readiness"] == {"ready_to_validate": False,
                                       "issues": ["La habilidad no tiene niveles configurados."]}
    assert (await _config(lab, empty.id))["data"]["levels"] == []


@pytest.mark.asyncio
async def test_unknown_skill_returns_404_on_every_skill_endpoint(lab):
    missing = uuid.uuid4()
    expected = {"statuscode": 404, "message": "Habilidad no encontrada", "data": None}
    for response in (
        await lab.client.get(f"{LAB}/skills/{missing}", headers=lab.admin),
        await lab.client.get(f"{LAB}/skills/{missing}/samples", headers=lab.admin),
        await lab.client.get(f"{LAB}/skills/{missing}/models", headers=lab.admin),
        await _upload(lab, missing, uuid.uuid4()),
    ):
        assert response.status_code == 404
        assert response.json() == expected
    missing_sample = await lab.client.delete(f"{LAB}/samples/{uuid.uuid4()}", headers=lab.admin)
    assert missing_sample.status_code == 404
    assert missing_sample.json() == {"statuscode": 404, "message": "Muestra no encontrada.", "data": None}
    assert _stored_files(lab) == []


# ---------------------------------------------------------------- samples (S3)


@pytest.mark.asyncio
async def test_training_sample_upload_list_delete_linked_to_level_and_criterion(lab):
    skill, _ = await _create_skill(lab)
    level_id = skill["levels"][0]["id"]
    content = b"training-video-content"
    response = await _upload(lab, skill["id"], level_id, criterion_key="postura", participant_id="P-01",
                             filename="toma.MOV", content=content)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["statuscode"] == 201
    assert body["message"] == "Muestra del laboratorio subida exitosamente."
    sample = body["data"]
    _assert_sample_shape(sample)
    assert {key: sample[key] for key in sample if key not in ("id", "created_at")} == {
        "skill_id": skill["id"], "skill_level_id": level_id, "criterion_key": "postura", "sample_role": "TRAINING",
        "file_format": "mov", "file_size_bytes": len(content), "participant_id": "P-01",
        "analysis_ready": False, "analysis_notes": [],
    }
    files = _stored_files(lab)
    assert [path.name for path in files] == [f"{sample['id']}.mov"]
    assert files[0].read_bytes() == content

    level_only = await _upload(lab, skill["id"], level_id, filename="otra.webm")
    assert level_only.status_code == 201, level_only.text
    assert level_only.json()["data"]["criterion_key"] is None
    assert level_only.json()["data"]["file_format"] == "webm"

    listed = await _samples(lab, skill["id"])
    assert listed["statuscode"] == 200 and listed["count"] == 2
    assert {item["id"] for item in listed["data"]} == {sample["id"], level_only.json()["data"]["id"]}
    for item in listed["data"]:
        _assert_sample_shape(item)

    level = (await _config(lab, skill["id"]))["data"]["levels"][0]
    assert level["training_samples"] == 2
    assert [(c["key"], c["training_samples"]) for c in level["criteria"]] == [("postura", 1), ("toques", 0)]

    # Legacy NOT NULL columns are filled from the catalog (visible through the generic dataset listing).
    legacy = (await lab.client.get("/api/ai/datasets/samples", headers=lab.admin)).json()["data"]
    stored = next(item for item in legacy if item["id"] == sample["id"])
    assert {key: stored[key] for key in ("discipline", "challenge", "hardware_info", "level_label",
                                          "file_hash_sha256", "signed_consent")} == {
        "discipline": "deportes", "challenge": "Dominadas", "hardware_info": "skill-lab-upload",
        "level_label": "Básico", "file_hash_sha256": hashlib.sha256(content).hexdigest(), "signed_consent": True,
    }

    deleted = await lab.client.delete(f"{LAB}/samples/{sample['id']}", headers=lab.admin)
    assert deleted.status_code == 200
    assert {key: deleted.json()[key] for key in ("statuscode", "message", "data")} == {
        "statuscode": 200, "message": "Muestra eliminada exitosamente.", "data": None}
    assert [path.name for path in _stored_files(lab)] == [f"{level_only.json()['data']['id']}.webm"]
    listed = await _samples(lab, skill["id"])
    assert listed["count"] == 1
    assert (await _config(lab, skill["id"]))["data"]["levels"][0]["criteria"][0]["training_samples"] == 0
    again = await lab.client.delete(f"{LAB}/samples/{sample['id']}", headers=lab.admin)
    assert again.status_code == 404


@pytest.mark.asyncio
async def test_reference_upload_replaces_previous_and_completes_readiness(lab):
    skill, _ = await _create_skill(lab)
    basic, advanced = skill["levels"][0]["id"], skill["levels"][1]["id"]
    first = (await _upload(lab, skill["id"], basic, role="REFERENCE", content=b"ref-1")).json()["data"]
    second_response = await _upload(lab, skill["id"], basic, role="REFERENCE", content=b"ref-2")
    assert second_response.status_code == 201
    second = second_response.json()["data"]
    assert second["sample_role"] == "REFERENCE" and second["criterion_key"] is None
    criterion_ref = (await _upload(lab, skill["id"], basic, role="REFERENCE", criterion_key="postura",
                                   content=b"ref-postura")).json()["data"]

    listed = await _samples(lab, skill["id"])
    assert {item["id"] for item in listed["data"]} == {second["id"], criterion_ref["id"]}
    assert sorted(path.name for path in _stored_files(lab)) == sorted(
        [f"{second['id']}.mp4", f"{criterion_ref['id']}.mp4"])
    assert not any(path.name.startswith(first["id"]) for path in _stored_files(lab))

    data = (await _config(lab, skill["id"]))["data"]
    level = data["levels"][0]
    assert level["reference"]["id"] == second["id"]
    _assert_sample_shape(level["reference"])
    assert level["training_samples"] == 0
    assert [(c["key"], c["has_reference"]) for c in level["criteria"]] == [("postura", True), ("toques", False)]
    assert data["readiness"] == {"ready_to_validate": False,
                                 "issues": ["El nivel «Avanzado» no tiene video de referencia."]}

    await _upload(lab, skill["id"], advanced, role="REFERENCE")
    assert (await _config(lab, skill["id"]))["data"]["readiness"] == {"ready_to_validate": True, "issues": []}


@pytest.mark.asyncio
async def test_invalid_uploads_are_rejected_without_rows_or_files(lab, monkeypatch):
    skill, _ = await _create_skill(lab)
    other, _ = await _create_skill(lab, name="Pases")
    basic = skill["levels"][0]["id"]
    cases = [
        (dict(level_id=other["levels"][0]["id"]), 404, "Nivel no encontrado para esta habilidad."),
        (dict(level_id=uuid.uuid4()), 404, "Nivel no encontrado para esta habilidad."),
        (dict(level_id=basic, criterion_key="inexistente"), 400, "El criterio indicado no existe en el nivel «Básico»."),
        (dict(level_id=skill["levels"][1]["id"], criterion_key="postura"), 400,
         "El criterio indicado no existe en el nivel «Avanzado»."),
        (dict(level_id=basic, role="VALIDATION"), 400, "El rol de la muestra debe ser TRAINING o REFERENCE."),
        (dict(level_id=basic, consent="false"), 400, "El consentimiento informado firmado es obligatorio."),
        (dict(level_id=basic, filename="clip.avi"), 400,
         "Formato no permitido: '.avi'. Solo se permiten archivos mov, mp4, webm."),
        (dict(level_id=basic, content=b""), 400, "El archivo de video está vacío."),
    ]
    for kwargs, status, message in cases:
        level_id = kwargs.pop("level_id")
        response = await _upload(lab, skill["id"], level_id, **kwargs)
        assert response.status_code == status, (kwargs, response.text)
        assert response.json() == {"statuscode": status, "message": message, "data": None}

    monkeypatch.setattr(skill_lab_service, "SKILL_LAB_MAX_FILE_SIZE_BYTES", 8)
    too_big = await _upload(lab, skill["id"], basic, content=b"123456789")
    assert too_big.status_code == 400
    assert too_big.json() == {"statuscode": 400, "data": None,
                              "message": "El tamaño del archivo supera el límite máximo permitido de 200 MB."}
    assert (await _samples(lab, skill["id"]))["count"] == 0
    assert _stored_files(lab) == []


def test_upload_limits_match_the_contract():
    assert skill_lab_service.SKILL_LAB_MAX_FILE_SIZE_BYTES == 200 * 1024 * 1024
    assert skill_lab_service.SKILL_LAB_ALLOWED_EXTENSIONS == {"mp4", "webm", "mov"}


@pytest.mark.asyncio
async def test_catalog_update_keeps_level_ids_so_lab_samples_stay_linked(lab):
    skill, payload = await _create_skill(lab)
    level_id = skill["levels"][0]["id"]
    sample = (await _upload(lab, skill["id"], level_id, criterion_key="postura")).json()["data"]
    levels = payload["levels"]
    levels[0]["name"] = "Básico renombrado"
    levels[0]["rubric"]["criteria"][0]["weight"] = 70
    levels[0]["rubric"]["criteria"][1]["weight"] = 30
    updated = await lab.client.put(f"/api/admin/catalog/skills/{skill['id']}", headers=lab.admin, json={
        **payload, "levels": levels[:1],
    })
    assert updated.status_code == 200, updated.text
    assert [level["name"] for level in updated.json()["data"]["levels"]] == ["Básico renombrado"]

    data = (await _config(lab, skill["id"]))["data"]
    assert [level["id"] for level in data["levels"]] == [level_id]
    assert data["levels"][0]["criteria"][0]["training_samples"] == 1
    assert data["levels"][0]["criteria"][0]["weight"] == 70.0
    assert (await _samples(lab, skill["id"]))["data"][0]["skill_level_id"] == level_id
    assert (await _samples(lab, skill["id"]))["data"][0]["id"] == sample["id"]


# ---------------------------------------------------------------- models (S5 storage, read side)


@pytest.mark.asyncio
async def test_models_list_only_returns_the_skill_validator_versions(lab):
    skill, _ = await _create_skill(lab)
    other, _ = await _create_skill(lab, name="Pases")
    rows = [
        ModelVersion(nombre="skill_validator", version="v1", ruta_onnx="", metricas={"loo_level_accuracy": 0.5},
                     activa=False, skill_id=uuid.UUID(skill["id"])),
        ModelVersion(nombre="skill_validator", version="v2", ruta_onnx="", metricas={"loo_level_accuracy": 0.8},
                     activa=True, skill_id=uuid.UUID(skill["id"])),
        ModelVersion(nombre="skill_validator", version="v1", ruta_onnx="", metricas={}, activa=True,
                     skill_id=uuid.UUID(other["id"])),
        ModelVersion(nombre="level_classifier", version="v9", ruta_onnx="x.onnx", metricas={}, activa=True),
    ]
    lab.db.add_all(rows)
    await lab.db.commit()

    response = await lab.client.get(f"{LAB}/skills/{skill['id']}/models", headers=lab.admin)
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    assert [(item["version"], item["activa"]) for item in body["data"]] == [("v2", True), ("v1", False)]
    for item in body["data"]:
        assert set(item) == {"id", "skill_id", "version", "activa", "metricas", "created_at"}
        assert item["skill_id"] == skill["id"]
    active = (await _config(lab, skill["id"]))["data"]["active_model"]
    assert active["id"] == str(rows[1].id) and active["metricas"] == {"loo_level_accuracy": 0.8}
