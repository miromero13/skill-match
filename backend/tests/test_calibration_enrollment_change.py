"""Regression for a calibration snapshot bound to an outdated enrollment."""
import pytest

from tests.test_evaluation_preflight import endpoint, isolated_db, scenario  # noqa: F401
from tests.test_evaluation_calibration import PAYLOAD, prepare
from app.services.calibration_vision_service import CalibrationVisionService


@pytest.mark.asyncio
async def test_enrollment_change_invalidates_previous_ready_state(scenario, monkeypatch):
    monkeypatch.setattr(CalibrationVisionService, "assess", lambda *args: {
        "lighting": True, "framing": True, "single_face": True, "microphone": True,
        "identity": True, "liveness": True, "passive_screen_check": True,
    })
    client, db, user, offer = scenario
    evaluation_id = await prepare(scenario)
    challenge = (await client.post(f"/api/evaluations/{evaluation_id}/liveness/challenge")).json()["data"]
    response = await client.post(f"/api/evaluations/{evaluation_id}/liveness/verify-identity",
                                json={**PAYLOAD, "challenge_id": challenge["id"]})
    assert response.status_code == 200 and response.json()["data"]["ready"] is True
    user.biometric_face_hash = "different-enrollment"
    await db.commit()
    response = await client.get(f"/api/evaluations/{evaluation_id}/environment/verify")
    assert response.status_code == 200
    state = response.json()["data"]
    assert state["ready"] is False and state["started_at"] is None
    assert state["status"] == "PENDING_CALIBRATION" and state["checks"] == {}
    quota = (await client.get(endpoint(offer, "preflight"))).json()["data"]
    assert quota["free_evaluations_left"] == 3 and quota["attempts_used"] == 0
