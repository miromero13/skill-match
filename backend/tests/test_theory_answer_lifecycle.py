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
    response = await client.post("/api/evaluations/start", json={"evaluation_id": key, "level_number": 1, "text_grading_consent": True})
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
    from app.services.theory_grading_provider import TheoryGradingProvider
    from app.schemas.theory_grading import ProviderGrade
    calls = []
    async def grade(self, **kwargs):
        calls.append(kwargs)
        return ProviderGrade(criteria=[{"criterion":"Mutability", "attainment":0.75, "reason":"Explains the distinction."}], feedback="Mostly correct.")
    monkeypatch.setattr(TheoryGradingProvider, "grade", grade)
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
    assert final["grading_state"] == "PENDING" and final["grading_score"] is None
    first = await client.post(f"/api/evaluations/{key}/grading/retry", json={})
    assert first.status_code == 200 and first.json()["message"] == "Corrección teórica procesada."
    assert first.json()["data"]["score"] == 75.0
    assert first.json()["data"]["state"] == "COMPLETE"
    assert len(calls) == 5
    assert all(set(call) == {"question", "reference", "transcript", "rubric"} for call in calls)
    replay = await client.post(f"/api/evaluations/{key}/grading/retry", json={})
    assert replay.status_code == 200 and replay.json() == first.json()
    assert len(calls) == 5
    assert (await client.get(f"/api/evaluations/{key}/result")).json() == first.json() | {"message":"Resultado de corrección recuperado exitosamente."}


@pytest.mark.asyncio
async def test_provider_failure_keeps_answers_and_attempt_pending_for_explicit_retry(scenario, monkeypatch):
    from app.services.local_speech_service import LocalSpeechService
    from app.services.theory_grading_provider import TheoryGradingProvider, GradingProviderError
    monkeypatch.setattr(LocalSpeechService, "transcribe", lambda raw: "Recorded explanation")
    async def fail(self, **kwargs):
        raise GradingProviderError("private provider payload")
    monkeypatch.setattr(TheoryGradingProvider, "grade", fail)
    _, _, _, offer = scenario
    preflight_path = endpoint(offer, "preflight")
    client, key = await started(scenario)
    started_before = (await client.post("/api/evaluations/start", json={"evaluation_id": key, "level_number": 1, "text_grading_consent": True})).json()
    attempts_before = await client.get(preflight_path)
    last_payload = None
    last_receipt = None
    for _ in range(5):
        progress = (await client.get(f"/api/evaluations/{key}/status")).json()["data"]
        last_payload = {"submission_id": str(uuid.uuid4()), "question_id": progress["current_question"]["id"], "audio_base64": audio()}
        last_receipt = await client.post(f"/api/evaluations/{key}/answers", json=last_payload)
    failure = await client.post(f"/api/evaluations/{key}/grading/retry", json={})
    assert failure.status_code == 503
    assert failure.json() == {"statuscode":503, "message":"No se pudo corregir la evaluación. Tu respuesta y tu intento permanecen guardados; podés reintentar.", "data":None}
    after = (await client.get(f"/api/evaluations/{key}/status")).json()["data"]
    assert after["grading_state"] == "ERROR" and after["grading_score"] is None and after["answered_count"] == 5
    assert (await client.post(f"/api/evaluations/{key}/answers", json=last_payload)).json() == last_receipt.json()
    result = (await client.get(f"/api/evaluations/{key}/result")).json()["data"]
    assert result["state"] == "ERROR" and result["score"] is None
    from app.core.config import settings
    from pydantic import SecretStr
    monkeypatch.setattr(settings, "THEORY_GRADING_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "THEORY_GRADING_MODEL", "different-model")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", SecretStr("other-key"))
    pinned = await client.post(f"/api/evaluations/{key}/grading/retry", json={})
    assert pinned.status_code == 503 and pinned.json()["data"] is None
    monkeypatch.setattr(settings, "THEORY_GRADING_PROVIDER", "openai")
    monkeypatch.setattr(settings, "THEORY_GRADING_MODEL", "mock-model")
    from app.schemas.theory_grading import ProviderGrade
    async def retry_same_provider(self, **kwargs):
        return ProviderGrade(criteria=[{"criterion":"Mutability", "attainment":0.75, "reason":"Explains distinction."}], feedback="Mostly correct.")
    monkeypatch.setattr(TheoryGradingProvider, "grade", retry_same_provider)
    retried = await client.post(f"/api/evaluations/{key}/grading/retry", json={})
    assert retried.status_code == 200
    assert retried.json()["data"]["provider"] == "openai"
    assert retried.json()["data"]["model"] == "mock-model"
    assert retried.json()["data"]["prompt_version"] == "theory-rubric-v1"
    started_after = (await client.post("/api/evaluations/start", json={"evaluation_id": key, "level_number": 1, "text_grading_consent": True})).json()
    attempts_after = await client.get(preflight_path)
    assert started_after["data"]["started_at"] == started_before["data"]["started_at"]
    assert attempts_after.status_code == attempts_before.status_code == 403
    assert attempts_after.json() == attempts_before.json()
    assert (await client.post(f"/api/evaluations/{key}/answers", json=last_payload)).json() == last_receipt.json()


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
