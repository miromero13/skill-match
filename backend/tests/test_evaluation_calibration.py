"""Calibration API checks reuse only the isolated preflight test fixtures."""
from datetime import datetime, timedelta, timezone

import pytest

from tests.test_evaluation_preflight import CONSENT, endpoint, isolated_db, scenario  # noqa: F401
from app.core.exceptions import SkillMatchException


PAYLOAD = {"frames": ["frame-a", "frame-b", "frame-c"],
           "audio_samples": [0.1] * 32, "camera_label": "Physical webcam"}


async def prepare(scenario):
    client, _, _, offer = scenario
    response = await client.post(endpoint(offer, "consent"), json=CONSENT)
    assert response.status_code == 200
    return response.json()["data"]["id"]


@pytest.mark.asyncio
async def test_challenge_requires_owned_consented_evaluation(scenario):
    client, _, _, offer = scenario
    response = await client.post(f"/api/evaluations/{offer.id}/liveness/challenge")
    assert response.status_code == 404
    evaluation_id = await prepare(scenario)
    client.headers.pop("Authorization")
    response = await client.post(f"/api/evaluations/{evaluation_id}/liveness/challenge")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_challenge_is_expiring_and_does_not_start_or_consume(scenario):
    client, _, _, offer = scenario
    evaluation_id = await prepare(scenario)
    response = await client.post(f"/api/evaluations/{evaluation_id}/liveness/challenge")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["action"] in ("TURN_LEFT", "TURN_RIGHT")
    expires = datetime.fromisoformat(data["expires_at"])
    assert 0 < (expires - datetime.now(timezone.utc)).total_seconds() <= 5
    state = await client.get(f"/api/evaluations/{evaluation_id}/environment/verify")
    assert state.json()["data"]["ready"] is False
    quota = (await client.get(endpoint(offer, "preflight"))).json()["data"]
    assert quota["free_evaluations_left"] == 3 and quota["attempts_used"] == 0


@pytest.mark.asyncio
async def test_success_is_single_use_and_never_starts_exam(scenario, monkeypatch):
    from app.services.calibration_vision_service import CalibrationVisionService
    monkeypatch.setattr(CalibrationVisionService, "assess", lambda *args: {
        "lighting": True, "framing": True, "single_face": True,
        "microphone": True, "identity": True, "liveness": True,
        "passive_screen_check": True,
    })
    client, _, _, offer = scenario
    evaluation_id = await prepare(scenario)
    challenge = (await client.post(f"/api/evaluations/{evaluation_id}/liveness/challenge")).json()["data"]
    body = {**PAYLOAD, "challenge_id": challenge["id"]}
    response = await client.post(f"/api/evaluations/{evaluation_id}/liveness/verify-identity", json=body)
    assert response.status_code == 200
    assert response.json()["data"]["ready"] is True
    again = await client.post(f"/api/evaluations/{evaluation_id}/liveness/verify-identity", json=body)
    assert again.status_code == 409
    state = (await client.get(f"/api/evaluations/{evaluation_id}/environment/verify")).json()["data"]
    assert state["ready"] is True and state["started_at"] is None
    quota = (await client.get(endpoint(offer, "preflight"))).json()["data"]
    assert quota["free_evaluations_left"] == 3 and quota["attempts_used"] == 0


@pytest.mark.asyncio
async def test_expired_challenge_cannot_authorize(scenario):
    from app.models.calibration import CalibrationChallenge
    client, db, _, _ = scenario
    evaluation_id = await prepare(scenario)
    challenge = (await client.post(f"/api/evaluations/{evaluation_id}/liveness/challenge")).json()["data"]
    from uuid import UUID
    stored = await db.get(CalibrationChallenge, UUID(challenge["id"]))
    stored.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db.commit()
    response = await client.post(f"/api/evaluations/{evaluation_id}/liveness/verify-identity",
                                 json={**PAYLOAD, "challenge_id": challenge["id"]})
    assert response.status_code == 410
    state = (await client.get(f"/api/evaluations/{evaluation_id}/environment/verify")).json()["data"]
    assert state["ready"] is False and state["started_at"] is None


@pytest.mark.asyncio
async def test_environment_rejection_does_not_authorize_or_consume(scenario, monkeypatch):
    from app.services.calibration_vision_service import CalibrationVisionService
    def reject(*args):
        raise SkillMatchException(statuscode=400, message="Iluminación insuficiente para la evaluación.")
    monkeypatch.setattr(CalibrationVisionService, "assess", reject)
    client, _, _, offer = scenario
    evaluation_id = await prepare(scenario)
    challenge = (await client.post(f"/api/evaluations/{evaluation_id}/liveness/challenge")).json()["data"]
    response = await client.post(f"/api/evaluations/{evaluation_id}/liveness/verify-identity",
                                 json={**PAYLOAD, "challenge_id": challenge["id"]})
    assert response.status_code == 400
    assert response.json() == {"statuscode": 400, "message": "Iluminación insuficiente para la evaluación.", "data": None}
    state = (await client.get(f"/api/evaluations/{evaluation_id}/environment/verify")).json()["data"]
    assert state["ready"] is False and state["started_at"] is None
    quota = (await client.get(endpoint(offer, "preflight"))).json()["data"]
    assert quota["free_evaluations_left"] == 3


@pytest.mark.asyncio
async def test_invalid_images_never_use_profile_synthetic_fallback(scenario):
    import base64
    client, _, _, offer = scenario
    evaluation_id = await prepare(scenario)
    challenge = (await client.post(f"/api/evaluations/{evaluation_id}/liveness/challenge")).json()["data"]
    body = {**PAYLOAD, "challenge_id": challenge["id"],
            "frames": [base64.b64encode(b"not-an-image" * 10).decode()] * 3}
    response = await client.post(f"/api/evaluations/{evaluation_id}/liveness/verify-identity", json=body)
    assert response.status_code == 400
    assert response.json()["data"] is None
    state = (await client.get(f"/api/evaluations/{evaluation_id}/environment/verify")).json()["data"]
    assert state["ready"] is False
    quota = (await client.get(endpoint(offer, "preflight"))).json()["data"]
    assert quota["free_evaluations_left"] == 3


@pytest.mark.asyncio
async def test_missing_models_fail_closed_without_consuming(scenario, monkeypatch, tmp_path):
    import base64
    import json
    import cv2
    import numpy as np
    import app.services.calibration_vision_service as vision
    client, db, user, offer = scenario
    user.biometric_embedding = json.dumps([1.0] + [0.0] * 127)
    await db.commit()
    monkeypatch.setattr(vision, "YUNET_MODEL_PATH", tmp_path / "missing.onnx")
    frames = []
    for value in (100, 110, 120):
        ok, encoded = cv2.imencode(".jpg", np.full((240, 320, 3), value, dtype=np.uint8))
        assert ok
        frames.append(base64.b64encode(encoded.tobytes()).decode())
    evaluation_id = await prepare(scenario)
    challenge = (await client.post(f"/api/evaluations/{evaluation_id}/liveness/challenge")).json()["data"]
    response = await client.post(f"/api/evaluations/{evaluation_id}/liveness/verify-identity",
                                 json={**PAYLOAD, "challenge_id": challenge["id"], "frames": frames})
    assert response.status_code == 503
    assert response.json() == {"statuscode": 503, "message": "Los modelos locales de calibración no están disponibles.", "data": None}
    state = (await client.get(f"/api/evaluations/{evaluation_id}/environment/verify")).json()["data"]
    assert state["ready"] is False and state["started_at"] is None
    assert (await client.get(endpoint(offer, "preflight"))).json()["data"]["free_evaluations_left"] == 3
