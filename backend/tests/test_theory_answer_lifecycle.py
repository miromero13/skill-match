"""Oral submissions are owned, timed and replay-safe through the public API."""
import base64
import io
import uuid
import wave

import pytest

from auth_catalog_fixtures import isolated_db
from test_evaluation_preflight import scenario, endpoint, CONSENT
from test_theory_exam_start import prepare, ready_runtime


def audio():
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\x10\x00" * 16000)
    return base64.b64encode(buffer.getvalue()).decode()


async def started(scenario):
    client, db, user, offer = scenario
    key = (await client.post(endpoint(offer, "consent"), json=CONSENT)).json()["data"]["id"]
    await prepare(db, user, offer, key)
    response = await client.post("/api/evaluations/start", json={"evaluation_id": key, "level_number": 1})
    assert response.status_code == 200
    return client, key


@pytest.mark.asyncio
async def test_status_has_server_clock_and_no_correction_material(scenario):
    client, key = await started(scenario)
    response = await client.get(f"/api/evaluations/{key}/status")
    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Estado del examen recuperado exitosamente."
    data = body["data"]
    assert data["status"] == "THEORY_ACTIVE" and data["answered_count"] == 0
    assert data["position"] == 1 and data["question_count"] == 5
    assert data["server_time"] and data["question_deadline_at"] and data["deadline_at"]
    assert "reference_answer" not in str(data) and "correct_choice" not in str(data)


@pytest.mark.asyncio
async def test_missing_transcription_is_explicit_and_does_not_record_an_answer(scenario, monkeypatch, tmp_path):
    from app.services.local_speech_service import LocalSpeechService
    monkeypatch.setattr(LocalSpeechService, "MODEL_DIR", tmp_path)
    client, key = await started(scenario)
    before = await client.get(f"/api/evaluations/{key}/status")
    assert before.status_code == 200
    question = before.json()["data"]["current_question"]
    submission = {"submission_id": str(uuid.uuid4()), "question_id": question["id"], "audio_base64": audio()}
    response = await client.post(f"/api/evaluations/{key}/answers", json=submission)
    assert response.status_code == 503
    assert response.json() == {"statuscode": 503, "message": "La transcripción local no está disponible. Tu respuesta no fue registrada.", "data": None}
    after = (await client.get(f"/api/evaluations/{key}/status")).json()["data"]
    assert after["answered_count"] == 0 and after["position"] == 1
    assert after["current_question"] == question
    assert after["question_deadline_at"] == before.json()["data"]["question_deadline_at"]


@pytest.mark.asyncio
async def test_client_transcript_is_not_accepted_as_an_oral_answer(scenario):
    client, key = await started(scenario)
    response = await client.post(f"/api/evaluations/{key}/answers", json={
        "submission_id": str(uuid.uuid4()), "question_id": str(uuid.uuid4()), "transcript": "A fake written answer",
    })
    assert response.status_code == 422
    assert response.json()["data"] is None
    state = await client.get(f"/api/evaluations/{key}/status")
    assert state.status_code == 200 and state.json()["data"]["answered_count"] == 0


@pytest.mark.asyncio
async def test_transcription_boundary_records_once_and_finishes_pending_review(scenario, monkeypatch):
    from app.services.local_speech_service import LocalSpeechService
    monkeypatch.setattr(LocalSpeechService, "transcribe", lambda raw: "Lists can be modified; tuples cannot.")
    client, key = await started(scenario)
    for index in range(5):
        state = (await client.get(f"/api/evaluations/{key}/status")).json()["data"]
        assert state["position"] == index + 1 and state["answered_count"] == index
        payload = {"submission_id": str(uuid.uuid4()), "question_id": state["current_question"]["id"], "audio_base64": audio()}
        first = await client.post(f"/api/evaluations/{key}/answers", json=payload)
        assert first.status_code == 200
        assert first.json()["message"] == "Respuesta oral registrada exitosamente."
        assert first.json()["data"]["transcript"] == "Lists can be modified; tuples cannot."
        replay = await client.post(f"/api/evaluations/{key}/answers", json=payload)
        assert replay.status_code == 200 and replay.json() == first.json()
        conflict = await client.post(f"/api/evaluations/{key}/answers", json={**payload, "audio_base64": base64.b64encode(b"changed").decode()})
        assert conflict.status_code == 409
        assert conflict.json() == {"statuscode": 409, "message": "El identificador de respuesta ya fue usado con otro contenido.", "data": None}
    final = (await client.get(f"/api/evaluations/{key}/status")).json()["data"]
    assert final["status"] == "THEORY_PENDING_REVIEW" and final["answered_count"] == 5
    assert final["current_question"] is None and final["question_deadline_at"] is None
    assert "score" not in final  # No semantic grader exists yet.


@pytest.mark.asyncio
async def test_question_and_global_timeouts_do_not_reset_on_reload(scenario, monkeypatch):
    from datetime import datetime, timedelta, timezone
    import app.services.theory_answer_service as module
    client, key = await started(scenario)
    before = (await client.get(f"/api/evaluations/{key}/status")).json()["data"]
    class Clock:
        @staticmethod
        def now(tz):
            return datetime.fromisoformat(before["deadline_at"]) + timedelta(seconds=1)
    monkeypatch.setattr(module, "datetime", Clock)
    after = (await client.get(f"/api/evaluations/{key}/status")).json()["data"]
    assert after["status"] == "THEORY_PENDING_REVIEW"
    assert after["answered_count"] == 0 and after["current_question"] is None
    replay = (await client.get(f"/api/evaluations/{key}/status")).json()["data"]
    assert replay == after
    rejected = await client.post(f"/api/evaluations/{key}/answers", json={
        "submission_id": str(uuid.uuid4()), "question_id": before["current_question"]["id"], "audio_base64": audio(),
    })
    assert rejected.status_code == 410
    assert rejected.json() == {"statuscode": 410, "message": "El tiempo para responder terminó.", "data": None}
    assert (await client.get(f"/api/evaluations/{key}/status")).json()["data"] == after
