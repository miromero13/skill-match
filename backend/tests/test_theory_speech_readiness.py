"""Presence of model files is not evidence that ASR preserves answer meaning."""
import pytest
from pydantic import SecretStr

from app.core.config import settings

from auth_catalog_fixtures import isolated_db
from test_evaluation_preflight import scenario, endpoint, CONSENT
from test_theory_exam_start import prepare
from app.services.local_speech_service import LocalSpeechService


@pytest.mark.asyncio
async def test_disabled_speech_runtime_cannot_consume_an_exam_attempt(scenario, monkeypatch, tmp_path):
    for name in ["encoder.onnx", "decoder.onnx", "tokens.txt"]:
        (tmp_path / name).write_bytes(b"present-but-not-approved")
    monkeypatch.setattr(settings, "THEORY_GRADING_PROVIDER", "openai")
    monkeypatch.setattr(settings, "THEORY_ASR_ENABLED", False)
    monkeypatch.setattr(settings, "THEORY_GRADING_MODEL", "mock-model")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", SecretStr("mock-key"))
    monkeypatch.setattr(LocalSpeechService, "MODEL_DIR", tmp_path)
    client, db, user, offer = scenario
    key = (await client.post(endpoint(offer, "consent"), json=CONSENT)).json()["data"]["id"]
    await prepare(db, user, offer, key)
    response = await client.post("/api/evaluations/start", json={"evaluation_id": key, "level_number": 1, "text_grading_consent": True})
    assert response.status_code == 503
    assert response.json() == {"statuscode": 503,
        "message": "La transcripción local está deshabilitada en la configuración. Tu intento no se descontó.", "data": None}
    state = (await client.get(endpoint(offer, "preflight"))).json()["data"]
    assert state["attempts_used"] == 0 and state["free_evaluations_left"] == 3
    assert state["pending_evaluation_id"] == key
