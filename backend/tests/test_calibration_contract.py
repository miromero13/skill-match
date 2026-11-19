"""T9b: the calibration contract (required evidence), persistence for supervision and the secrets never leaving.

Written after the contract change for the request shape (the old shape was accepted before: a RED run of these is not
available); the model/persistence/gating tests were written against behavior that did not exist yet.
"""
import json
import uuid

import pytest
from sqlalchemy import select

from tests.test_evaluation_preflight import CONSENT, endpoint, isolated_db, scenario  # noqa: F401
from tests.test_calibration_audio import consented
from tests.test_evaluation_calibration import PAYLOAD, passing_output, prepare
from app.models.calibration import CalibrationChallenge
from app.services.integrity import messages as m
from test_integrity_calibration import http_body

URL = "/liveness/verify-identity"
STATE_KEYS = {"evaluation_id", "ready", "status", "started_at", "checks"}


async def state_of(client, root):
    return (await client.get(root + "/environment/verify")).json()["data"]


@pytest.mark.asyncio
async def test_the_old_shape_request_is_rejected_with_a_spanish_message_and_never_ready(scenario, monkeypatch):
    client, offer, root, challenge, good = await consented(scenario, monkeypatch)
    old = {key: value for key, value in http_body(good, challenge["id"]).items() if key not in ("gaze_points", "mouth_samples")}
    response = await client.post(root + URL, json=old)
    assert response.status_code == 422
    message = response.json()["message"]
    assert "gaze_points" in message and "mouth_samples" in message and "obligatorio" in message
    assert response.json()["data"] is None
    assert (await state_of(client, root))["ready"] is False


def mutate(body, **changes):
    return {**body, **changes}


INVALID = {
    "no gaze points": lambda b: mutate(b, gaze_points=[]),
    "four gaze points": lambda b: mutate(b, gaze_points=b["gaze_points"][:4]),
    "repeated target": lambda b: mutate(b, gaze_points=[b["gaze_points"][0]] * 5),
    "unknown target": lambda b: mutate(b, gaze_points=[{**b["gaze_points"][0], "target": "MIDDLE"}, *b["gaze_points"][1:]]),
    "empty target frames": lambda b: mutate(b, gaze_points=[{**b["gaze_points"][0], "frames": []}, *b["gaze_points"][1:]]),
    "too many target frames": lambda b: mutate(b, gaze_points=[{**b["gaze_points"][0], "frames": ["a"] * 7}, *b["gaze_points"][1:]]),
    "huge target frame": lambda b: mutate(b, gaze_points=[{**b["gaze_points"][0], "frames": ["a" * 200_001]}, *b["gaze_points"][1:]]),
    "no mouth samples": lambda b: mutate(b, mouth_samples=[]),
    "too few mouth samples": lambda b: mutate(b, mouth_samples=b["mouth_samples"][:7]),
    "too many mouth samples": lambda b: mutate(b, mouth_samples=[{"t_ms": i, "mouth_open": 0.1} for i in range(451)]),
    "mouth aperture out of range": lambda b: mutate(b, mouth_samples=[{**b["mouth_samples"][0], "mouth_open": 3}, *b["mouth_samples"][1:]]),
    "mouth samples too dense": lambda b: mutate(b, mouth_samples=[{"t_ms": i * 10, "mouth_open": 0.1} for i in range(20)]),
    "mouth samples past the audio": lambda b: mutate(b, mouth_samples=[*b["mouth_samples"][:-1], {"t_ms": 9000, "mouth_open": 0.1}]),
    "extra field": lambda b: mutate(b, gaze_zone={"pitch_min": 0}),
}


@pytest.mark.asyncio
@pytest.mark.parametrize("name", list(INVALID))
async def test_each_new_piece_of_evidence_is_required_and_bounded(scenario, monkeypatch, name):
    client, offer, root, challenge, good = await consented(scenario, monkeypatch)
    response = await client.post(root + URL, json=INVALID[name](http_body(good, challenge["id"])))
    assert response.status_code == 422 and response.json()["data"] is None
    assert (await state_of(client, root))["ready"] is False
    # Nothing was consumed: the same challenge still verifies a valid request.
    assert (await client.post(root + URL, json=http_body(good, challenge["id"]))).status_code == 200


@pytest.mark.asyncio
async def test_success_persists_the_supervision_inputs_and_never_returns_them(scenario, monkeypatch):
    client, offer, root, challenge, good = await consented(scenario, monkeypatch)
    response = await client.post(root + URL, json=http_body(good, challenge["id"]))
    assert response.status_code == 200
    data = response.json()["data"]
    assert set(data) == STATE_KEYS and data["ready"] is True
    from app.services.evaluation_calibration_service import EvaluationCalibrationService as Service
    assert set(data["checks"]) == Service.REQUIRED_CHECKS and all(data["checks"].values())
    again = (await client.get(root + "/environment/verify")).json()["data"]
    assert set(again) == STATE_KEYS
    for body in (data, again):  # the checks are booleans (their names are public); nothing else may carry a secret
        assert all(value is True for value in body["checks"].values())
        raw = json.dumps({**body, "checks": None})
        for secret in ("embedding", "zone", "pitch_min", "occlusion", "ambient_rms", "skin_cr", "0.6", "0.8"):
            assert secret not in raw
    db = scenario[1]
    row = (await db.execute(select(CalibrationChallenge).where(CalibrationChallenge.id == uuid.UUID(challenge["id"])))).scalar_one()
    assert row.gaze_zone["yaw_min"] < 0 < row.gaze_zone["yaw_max"]
    assert row.voiceprint["embedding"] and row.voiceprint["ambient_rms"] >= 0 and row.occlusion_ref["n"] >= 3


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", ["gaze_zone", "voiceprint", "occlusion_ref"])
async def test_ready_needs_the_three_supervision_inputs_no_clean_pass_by_omission(scenario, monkeypatch, missing):
    client, offer, root, challenge, good = await consented(scenario, monkeypatch)
    assert (await client.post(root + URL, json=http_body(good, challenge["id"]))).status_code == 200
    db = scenario[1]
    row = (await db.execute(select(CalibrationChallenge).where(CalibrationChallenge.id == uuid.UUID(challenge["id"])))).scalar_one()
    setattr(row, missing, None)
    await db.commit()
    state = await state_of(client, root)
    assert state["ready"] is False and state["status"] == "PENDING_CALIBRATION"


@pytest.mark.asyncio
async def test_an_incomplete_engine_verdict_is_never_stored_or_consumed(scenario, monkeypatch):
    from app.services.calibration_vision_service import CalibrationVisionService
    client, offer, root, challenge, good = await consented(scenario, monkeypatch)
    short = passing_output()
    short.checks.pop("voiceprint")
    monkeypatch.setattr(CalibrationVisionService, "assess", lambda *args: short)
    response = await client.post(root + URL, json=http_body(good, challenge["id"]))
    assert response.json() == {"statuscode": 400, "message": m.INCOMPLETE, "data": None}
    assert (await state_of(client, root))["ready"] is False


# ---- the speaker model is required: no voiceprint, no READY (L14: it is not installed on this machine) --------------


def engine_without_speaker_models(good, tmp_path, monkeypatch, diarize=False):
    """The engine over the real speaker-model loaders pointed at files that do not exist."""
    from app.services import calibration_speaker_service as speakers
    from app.services.integrity import calibration as cal, thresholds as t, voiceprint as vp
    from app.services.integrity.audio_analyzer import AudioAnalyzer
    missing = tmp_path / "missing.onnx"
    monkeypatch.setattr(speakers, "SEGMENTATION_MODEL", missing)
    monkeypatch.setattr(speakers, "EMBEDDING_MODEL", missing)
    monkeypatch.setattr(vp, "EMBEDDING_MODEL", missing)
    extractor = vp.default_extractor()
    audio = AudioAnalyzer(good.fake.state, speaker_segments=(lambda a: good.segments(a)) if diarize else None,
                          extractor=extractor, vad_floor=0.0, min_speaker_s=t.CAL_SPEAKER_MIN_DURATION_S)
    return cal.CalibrationEngine(good.fake, audio, extractor)


@pytest.mark.parametrize("diarize,check", [(False, "single_speaker"), (True, "voiceprint")])
def test_a_missing_speaker_model_fails_closed_with_503_at_whichever_step_needs_it(monkeypatch, tmp_path, diarize, check):
    from test_integrity_calibration import Calibration
    good = Calibration(monkeypatch)
    from app.services.integrity import calibration as cal
    with pytest.raises(cal.CalibrationRejected) as caught:
        engine_without_speaker_models(good, tmp_path, monkeypatch, diarize).assess(good.evidence())
    assert (caught.value.check, caught.value.status, caught.value.message) == (check, 503, m.SPEAKER_MODELS_UNAVAILABLE)


@pytest.mark.asyncio
async def test_without_the_speaker_model_the_calibration_is_503_not_ready_and_keeps_the_challenge(
        scenario, monkeypatch, tmp_path):
    from app.services.calibration_vision_service import CalibrationVisionService
    client, offer, root, challenge, good = await consented(scenario, monkeypatch)
    monkeypatch.setattr(CalibrationVisionService, "engine",
                        staticmethod(lambda: engine_without_speaker_models(good, tmp_path, monkeypatch, diarize=True)))
    response = await client.post(root + URL, json=http_body(good, challenge["id"]))
    assert response.json() == {"statuscode": 503, "message": m.SPEAKER_MODELS_UNAVAILABLE, "data": None}
    assert (await state_of(client, root))["ready"] is False
    monkeypatch.setattr(CalibrationVisionService, "engine", staticmethod(good.engine))
    assert (await client.post(root + URL, json=http_body(good, challenge["id"]))).status_code == 200


# ---- READY still gates the theory exam ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", ["gaze_zone", "voiceprint", "occlusion_ref"])
async def test_theory_start_needs_the_supervision_inputs_of_the_calibration(scenario, missing):
    from tests.test_theory_exam_start import prepare as prepare_exam
    client, db, user, offer = scenario
    evaluation_id = (await client.post(endpoint(offer, "consent"), json=CONSENT)).json()["data"]["id"]
    await prepare_exam(db, user, offer, evaluation_id)
    row = (await db.execute(select(CalibrationChallenge))).scalars().one()
    setattr(row, missing, None)
    await db.commit()
    rejected = await client.post("/api/evaluations/start", json={"evaluation_id": evaluation_id, "level_number": 1})
    assert rejected.status_code == 409
    assert rejected.json() == {"statuscode": 409, "message": "Completá una calibración válida antes de iniciar el examen.", "data": None}
