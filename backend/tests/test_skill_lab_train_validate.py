"""Skill lab T4 (S3-S7): analysis caching, train (`skill_validator` per skill) and validate, through HTTP.

Same hygiene as `test_skill_lab_api.py` (reused `lab` fixture): throwaway PostgreSQL schema rolled back,
stored files and temp copies under the pytest tmp path, `analyze_video` replaced by the synthetic
`FakeAnalyzer` unless a test explicitly restores the real engine (only for unreadable bytes, which never
reach the pose model).
"""
# ruff: noqa: F811 - pytest fixtures (`lab`, `isolated_db`) are imported and then requested by name.
import uuid

import pytest
from sqlalchemy import select

from app.core.exceptions import SkillMatchException
from app.models.dataset_sample import DatasetSample
from app.services import skill_lab_service
from app.skill_validation import ENGINE_VERSION, METRIC_TYPES, analyze_video as real_analyze_video
from auth_catalog_fixtures import isolated_db  # noqa: F401 - required by `lab`
from test_skill_lab_api import (  # noqa: F401 - `lab` is a fixture
    LAB,
    NOT_FOUND,
    _create_skill,
    _samples,
    _stored_files,
    _upload,
    lab,
    video_bytes,
)

UNREADABLE_NOTE = "No se pudo leer el video (formato no soportado o archivo dañado)."
RESULT_KEYS = {
    "skill_id", "skill_name", "engine_version", "model_version", "analysis_complete", "target_level_id",
    "achieved_level", "score", "min_approval_threshold", "meets_skill_threshold", "approved",
    "model_level_estimate", "levels", "pose_detected_ratio", "duration_seconds", "notes",
}
MODEL_KEYS = {"id", "skill_id", "version", "activa", "metricas", "created_at"}

POSE_LEVELS = [
    {"level_number": 1, "name": "Básico", "rubric": {"min_score": 60, "criteria": []}},
    {"level_number": 2, "name": "Avanzado", "rubric": {"min_score": 70, "criteria": []}},
]


async def _pose_skill(ctx, name="Movimientos", threshold=70, references=("juggle", "squat")):
    """Two criterion-less levels (implicit REFERENCE_REPLICATION): L1 juggle reference, L2 squat reference."""
    skill, _ = await _create_skill(ctx, name=name, min_approval_threshold=threshold, levels=POSE_LEVELS)
    for level, motion in zip(skill["levels"], references):
        if motion is not None:
            response = await _upload(ctx, skill["id"], level["id"], role="REFERENCE", content=video_bytes(motion))
            assert response.status_code == 201, response.text
    return skill


async def _train(ctx, skill_id, headers=None):
    return await ctx.client.post(f"{LAB}/skills/{skill_id}/train", headers=ctx.admin if headers is None else headers)


async def _validate(ctx, skill_id, content, *, level_id=None, filename="intento.mp4", headers=None):
    data = {"skill_level_id": str(level_id)} if level_id is not None else {}
    return await ctx.client.post(
        f"{LAB}/skills/{skill_id}/validate",
        headers=ctx.admin if headers is None else headers,
        data=data,
        files={"file": (filename, content, "video/mp4")},
    )


async def _models(ctx, skill_id):
    response = await ctx.client.get(f"{LAB}/skills/{skill_id}/models", headers=ctx.admin)
    assert response.status_code == 200, response.text
    return response.json()


def _validation(response):
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["statuscode"] == 200 and body["message"] == "Validación completada."
    assert set(body["data"]) == RESULT_KEYS
    return body["data"]


def _levels(result):
    return {level["level_id"]: level for level in result["levels"]}


def _use_real_engine(ctx, monkeypatch):
    monkeypatch.setattr(skill_lab_service, "analyze_video", real_analyze_video)


# ---------------------------------------------------------------- metric types (engine catalog)


@pytest.mark.asyncio
async def test_metric_types_come_from_the_engine(lab):
    response = await lab.client.get(f"{LAB}/metric-types", headers=lab.admin)
    assert response.status_code == 200
    assert response.json()["data"] == METRIC_TYPES
    assert response.json()["count"] == len(METRIC_TYPES)


# ---------------------------------------------------------------- analysis caching (S3, S4)


@pytest.mark.asyncio
async def test_upload_analyzes_with_the_passes_the_skill_needs(lab):
    # L1 mixes REFERENCE_REPLICATION + BALL_TOUCH_STREAK, L2 has no criteria (implicit replication).
    skill, _ = await _create_skill(lab)
    basic, advanced = skill["levels"][0]["id"], skill["levels"][1]["id"]

    reference = await _upload(lab, skill["id"], basic, role="REFERENCE", content=video_bytes("juggle"))
    training_l1 = await _upload(lab, skill["id"], basic, criterion_key="toques", content=video_bytes(streak=8))
    training_l2 = await _upload(lab, skill["id"], advanced, content=video_bytes("squat"))
    for response in (reference, training_l1, training_l2):
        assert response.status_code == 201, response.text
        assert response.json()["data"]["analysis_ready"] is True
        assert response.json()["data"]["analysis_notes"] == []
    passes = [(call["name"].split(".")[0], call["need_pose"], call["need_ball"]) for call in lab.analyzer.calls]
    assert passes == [
        # References are only compared by pose.
        (reference.json()["data"]["id"], True, False),
        # TRAINING samples get every pass the skill measures (tolerance negatives + level estimator).
        (training_l1.json()["data"]["id"], True, True),
        (training_l2.json()["data"]["id"], True, True),
    ]
    assert all(item["analysis_ready"] for item in (await _samples(lab, skill["id"]))["data"])

    pose_only = await _pose_skill(lab, name="Solo pose", references=(None, None))
    lab.analyzer.calls.clear()
    await _upload(lab, pose_only["id"], pose_only["levels"][0]["id"], content=video_bytes())
    assert [(c["need_pose"], c["need_ball"]) for c in lab.analyzer.calls] == [(True, False)]


@pytest.mark.asyncio
async def test_analysis_failure_never_fails_the_upload(lab, monkeypatch):
    skill = await _pose_skill(lab, references=(None, None))

    def broken(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(skill_lab_service, "analyze_video", broken)
    response = await _upload(lab, skill["id"], skill["levels"][0]["id"], content=video_bytes())
    assert response.status_code == 201, response.text
    assert response.json()["data"]["analysis_ready"] is False
    assert response.json()["data"]["analysis_notes"] == []
    assert (await _samples(lab, skill["id"]))["count"] == 1


@pytest.mark.asyncio
async def test_unreadable_upload_is_kept_with_the_engine_notes(lab, monkeypatch):
    skill = await _pose_skill(lab, references=(None, None))
    _use_real_engine(lab, monkeypatch)
    response = await _upload(lab, skill["id"], skill["levels"][0]["id"], role="REFERENCE", content=b"corrupt")
    assert response.status_code == 201, response.text
    sample = response.json()["data"]
    assert sample["analysis_ready"] is True
    assert sample["analysis_notes"] == [UNREADABLE_NOTE]
    readiness = (await lab.client.get(f"{LAB}/skills/{skill['id']}", headers=lab.admin)).json()["data"]["readiness"]
    assert readiness == {"ready_to_validate": False, "issues": [
        "El video de referencia del nivel «Básico» no tiene una pose utilizable; vuelve a subirlo.",
        "El nivel «Avanzado» no tiene video de referencia.",
    ]}


@pytest.mark.asyncio
async def test_train_recomputes_only_missing_or_stale_analyses(lab):
    skill = await _pose_skill(lab)
    level_id = skill["levels"][0]["id"]
    ids = [(await _upload(lab, skill["id"], level_id, content=video_bytes(seed=i + 1))).json()["data"]["id"]
           for i in range(3)]
    rows = {str(row.id): row for row in (await lab.db.execute(
        select(DatasetSample).where(DatasetSample.id.in_([uuid.UUID(i) for i in ids])))).scalars()}
    rows[ids[0]].analysis = None
    rows[ids[1]].analysis = {**rows[ids[1]].analysis, "engine_version": "old-engine"}
    await lab.db.commit()
    stale = await _samples(lab, skill["id"])
    assert {item["id"]: item["analysis_ready"] for item in stale["data"] if item["id"] in ids} == {
        ids[0]: False, ids[1]: False, ids[2]: True}

    lab.analyzer.calls.clear()
    assert (await _train(lab, skill["id"])).status_code == 201
    assert sorted(call["name"].split(".")[0] for call in lab.analyzer.calls) == sorted(ids[:2])
    assert all(item["analysis_ready"] for item in (await _samples(lab, skill["id"]))["data"])

    lab.analyzer.calls.clear()
    assert (await _train(lab, skill["id"])).status_code == 201
    assert lab.analyzer.calls == []


# ---------------------------------------------------------------- train (S5)


@pytest.mark.asyncio
async def test_train_creates_active_versions_and_deactivates_the_previous_one(lab):
    skill = await _pose_skill(lab)
    basic, advanced = skill["levels"][0]["id"], skill["levels"][1]["id"]
    for seed in (1, 2):
        await _upload(lab, skill["id"], basic, content=video_bytes("juggle", seed=seed, yaw=20.0 * seed))
    await _upload(lab, skill["id"], advanced, content=video_bytes("squat", seed=3))

    first = await _train(lab, skill["id"])
    assert first.status_code == 201, first.text
    body = first.json()
    assert body["statuscode"] == 201 and body["message"] == "Modelo de la habilidad entrenado exitosamente."
    v1 = body["data"]
    assert set(v1) == MODEL_KEYS
    assert (v1["skill_id"], v1["version"], v1["activa"]) == (skill["id"], "v1", True)
    metrics = v1["metricas"]
    assert metrics["engine_version"] == ENGINE_VERSION
    assert metrics["samples_per_level"] == {basic: 2, advanced: 1}
    assert metrics["samples_total"] == 3
    assert "loo_level_accuracy" in metrics and isinstance(metrics["notes"], list)
    assert "Se recomienda al menos 3 videos por nivel." in metrics["notes"]
    assert "calibration" not in metrics

    second = await _train(lab, skill["id"])
    assert second.status_code == 201, second.text
    v2 = second.json()["data"]
    assert (v2["version"], v2["activa"]) == ("v2", True)
    listed = await _models(lab, skill["id"])
    assert [(item["id"], item["version"], item["activa"]) for item in listed["data"]] == [
        (v2["id"], "v2", True), (v1["id"], "v1", False)]
    config = (await lab.client.get(f"{LAB}/skills/{skill['id']}", headers=lab.admin)).json()["data"]
    assert config["active_model"]["id"] == v2["id"]
    assert config["readiness"] == {"ready_to_validate": True, "issues": []}

    # Versions are per skill.
    other = await _pose_skill(lab, name="Otra")
    assert (await _train(lab, other["id"])).json()["data"]["version"] == "v1"
    assert [item["activa"] for item in (await _models(lab, skill["id"]))["data"]] == [True, False]


@pytest.mark.asyncio
async def test_train_without_training_videos_stores_a_default_calibration(lab):
    skill = await _pose_skill(lab)
    response = await _train(lab, skill["id"])
    assert response.status_code == 201, response.text
    model = response.json()["data"]
    assert (model["version"], model["activa"]) == ("v1", True)
    assert model["metricas"]["samples_total"] == 0
    assert model["metricas"]["samples_per_level"] == {level["id"]: 0 for level in skill["levels"]}
    assert "No hay videos de entrenamiento; se usan las tolerancias por defecto." in model["metricas"]["notes"]


# ---------------------------------------------------------------- validate (S6)


@pytest.mark.asyncio
async def test_validate_scores_a_matching_motion_and_rejects_a_different_one(lab):
    skill = await _pose_skill(lab)
    basic, advanced = skill["levels"][0]["id"], skill["levels"][1]["id"]
    await _upload(lab, skill["id"], advanced, content=video_bytes("squat", seed=2))
    await _train(lab, skill["id"])
    samples_before = (await _samples(lab, skill["id"]))["count"]
    files_before = _stored_files(lab)

    result = _validation(await _validate(lab, skill["id"], video_bytes("squat", seed=7, yaw=30.0)))
    assert (result["skill_id"], result["skill_name"], result["engine_version"], result["model_version"]) == (
        skill["id"], "Movimientos", ENGINE_VERSION, "v1")
    assert result["analysis_complete"] is True and result["target_level_id"] is None
    assert result["achieved_level"] == {"level_id": advanced, "level_number": 2, "name": "Avanzado"}
    levels = _levels(result)
    assert levels[advanced]["passed"] is True and levels[advanced]["score"] >= 70
    assert levels[basic]["passed"] is False
    assert result["score"] == levels[advanced]["score"]
    assert result["min_approval_threshold"] == 70.0
    assert result["approved"] is True and result["meets_skill_threshold"] is True
    assert [c["metric_type"] for c in levels[advanced]["criteria"]] == ["REFERENCE_REPLICATION"]

    different = _validation(await _validate(lab, skill["id"], video_bytes("jack", seed=5)))
    assert different["achieved_level"] is None
    assert different["approved"] is False
    assert different["score"] == _levels(different)[basic]["score"] < 30

    # Nothing is persisted: no rows, no stored files, no temp copies left.
    assert (await _samples(lab, skill["id"]))["count"] == samples_before
    assert _stored_files(lab) == files_before
    assert list(lab.temp_dir.iterdir()) == []
    assert (await _models(lab, skill["id"]))["count"] == 1


@pytest.mark.asyncio
async def test_validate_without_a_model_and_a_level_without_reference(lab):
    skill = await _pose_skill(lab, references=("juggle", None))
    basic, advanced = skill["levels"][0]["id"], skill["levels"][1]["id"]
    result = _validation(await _validate(lab, skill["id"], video_bytes("juggle", seed=4)))
    assert result["model_version"] is None
    levels = _levels(result)
    assert levels[advanced]["evaluable"] is False and levels[advanced]["score"] is None
    assert levels[advanced]["not_evaluable_reason"] == "El nivel no tiene un video de referencia cargado."
    assert levels[advanced]["criteria"][0]["score"] is None
    assert levels[basic]["passed"] is True
    assert result["achieved_level"]["level_id"] == basic


@pytest.mark.asyncio
async def test_validate_target_level_restricts_evaluation_and_analysis_passes(lab):
    skill, _ = await _create_skill(lab)  # L1 replication + ball (target 20), L2 implicit replication
    basic, advanced = skill["levels"][0]["id"], skill["levels"][1]["id"]
    await _upload(lab, skill["id"], basic, role="REFERENCE", content=video_bytes("juggle"))
    await _upload(lab, skill["id"], advanced, role="REFERENCE", content=video_bytes("squat"))

    lab.analyzer.calls.clear()
    targeted = _validation(await _validate(lab, skill["id"], video_bytes("squat", seed=3), level_id=advanced))
    assert targeted["target_level_id"] == advanced
    assert [level["level_id"] for level in targeted["levels"]] == [advanced]
    assert targeted["achieved_level"]["level_id"] == advanced
    assert [(c["need_pose"], c["need_ball"]) for c in lab.analyzer.calls] == [(True, False)]

    lab.analyzer.calls.clear()
    full = _validation(await _validate(lab, skill["id"], video_bytes("juggle", seed=3, streak=10)))
    assert [(c["need_pose"], c["need_ball"]) for c in lab.analyzer.calls] == [(True, True)]
    criteria = {c["key"]: c for c in _levels(full)[basic]["criteria"]}
    assert criteria["toques"]["score"] == 50.0 and criteria["toques"]["detail"]["max_streak"] == 10
    assert criteria["postura"]["score"] >= 90
    assert _levels(full)[basic]["score"] == pytest.approx(0.6 * criteria["postura"]["score"] + 0.4 * 50.0, abs=0.01)

    other, _ = await _create_skill(lab, name="Pases")
    for level_id in (other["levels"][0]["id"], uuid.uuid4()):
        response = await _validate(lab, skill["id"], video_bytes(), level_id=level_id)
        assert response.status_code == 404
        assert response.json() == {"statuscode": 404, "message": "Nivel no encontrado para esta habilidad.",
                                   "data": None}
    missing = await _validate(lab, uuid.uuid4(), video_bytes())
    assert missing.status_code == 404
    assert missing.json() == {"statuscode": 404, "message": "Habilidad no encontrada", "data": None}
    assert list(lab.temp_dir.iterdir()) == []


@pytest.mark.asyncio
async def test_unreadable_empty_or_oversized_videos_still_return_200_with_score_zero(lab, monkeypatch):
    skill = await _pose_skill(lab)
    _use_real_engine(lab, monkeypatch)
    corrupt = _validation(await _validate(lab, skill["id"], b"corrupt-bytes"))
    assert corrupt["analysis_complete"] is False
    assert (corrupt["score"], corrupt["approved"], corrupt["achieved_level"]) == (0.0, False, None)
    assert corrupt["notes"] == [UNREADABLE_NOTE]

    calls = []
    monkeypatch.setattr(skill_lab_service, "analyze_video", lambda *a, **k: calls.append(a))
    empty = _validation(await _validate(lab, skill["id"], b""))
    assert (empty["analysis_complete"], empty["score"], empty["approved"]) == (False, 0.0, False)
    assert empty["notes"] == ["El archivo recibido está vacío."]

    monkeypatch.setattr(skill_lab_service, "SKILL_LAB_MAX_FILE_SIZE_BYTES", 8)
    oversize = _validation(await _validate(lab, skill["id"], b"123456789"))
    assert (oversize["analysis_complete"], oversize["score"], oversize["approved"]) == (False, 0.0, False)
    assert oversize["notes"] == ["El video supera el tamaño máximo de 200 MB; no se analizó."]
    assert all(level["passed"] is False for level in oversize["levels"])

    assert calls == []
    assert list(lab.temp_dir.iterdir()) == []
    assert (await _models(lab, skill["id"]))["count"] == 0


@pytest.mark.asyncio
async def test_validate_skill_video_is_the_member_flow_entry_point(lab, tmp_path):
    skill = await _pose_skill(lab)
    await _train(lab, skill["id"])
    video = tmp_path / "member-attempt.mp4"
    video.write_bytes(video_bytes("juggle", seed=6, yaw=-25.0))

    result = await skill_lab_service.validate_skill_video(lab.db, uuid.UUID(skill["id"]), video)
    assert set(result) == RESULT_KEYS
    assert result["model_version"] == "v1"
    assert result["achieved_level"]["level_id"] == skill["levels"][0]["id"]
    assert result["approved"] is True
    assert video.read_bytes() == video_bytes("juggle", seed=6, yaw=-25.0)

    targeted = await skill_lab_service.validate_skill_video(
        lab.db, uuid.UUID(skill["id"]), str(video), target_level_id=uuid.UUID(skill["levels"][1]["id"]))
    assert [level["level_id"] for level in targeted["levels"]] == [skill["levels"][1]["id"]]
    assert targeted["achieved_level"] is None and targeted["approved"] is False

    missing_file = await skill_lab_service.validate_skill_video(lab.db, uuid.UUID(skill["id"]), tmp_path / "nope.mp4")
    assert missing_file["analysis_complete"] is False and missing_file["score"] == 0.0

    with pytest.raises(SkillMatchException) as raised:
        await skill_lab_service.validate_skill_video(lab.db, uuid.uuid4(), video)
    assert (raised.value.statuscode, raised.value.message) == (404, "Habilidad no encontrada")


# ---------------------------------------------------------------- admin only (S7)


@pytest.mark.asyncio
@pytest.mark.parametrize("who", ["anonymous", "member"])
async def test_train_and_validate_are_hidden_from_members_and_anonymous(lab, who):
    skill = await _pose_skill(lab)
    headers = {} if who == "anonymous" else lab.member
    lab.analyzer.calls.clear()
    for response in (await _train(lab, skill["id"], headers=headers),
                     await _validate(lab, skill["id"], video_bytes(), headers=headers)):
        assert response.status_code == 404
        assert response.json() == NOT_FOUND
    assert lab.analyzer.calls == []
    assert (await _models(lab, skill["id"]))["count"] == 0
    assert list(lab.temp_dir.iterdir()) == []
