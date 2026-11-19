"""Actual exam starts consume one attempt only after all prerequisites pass."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from auth_catalog_fixtures import isolated_db
from test_evaluation_preflight import scenario, endpoint, CONSENT
from test_theory_question_publication import complete
from app.models import CalibrationChallenge, Evaluation, SkillLevel
from app.models.theory_question import TheoryQuestion
from app.services.evaluation_calibration_service import EvaluationCalibrationService


@pytest.fixture(autouse=True)
def ready_runtime(monkeypatch):
    from pydantic import SecretStr
    from app.core.config import settings
    from app.services.theory_exam_service import TheoryExamService
    monkeypatch.setattr(TheoryExamService, "check_runtime", staticmethod(lambda: None))
    monkeypatch.setattr(settings, "THEORY_GRADING_PROVIDER", "openai")
    monkeypatch.setattr(settings, "THEORY_GRADING_MODEL", "mock-model")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", SecretStr("mock-key"))


async def prepare(db, user, offer, evaluation_id, count=5):
    evaluation = await db.get(Evaluation, uuid.UUID(evaluation_id))
    evaluation.status = "READY_FOR_THEORY"
    db.add(SkillLevel(skill_id=offer.skill_id, level_number=1, name="Principiante"))
    now = datetime.now(timezone.utc)
    db.add(CalibrationChallenge(evaluation_id=evaluation.id, action="TURN_LEFT",
                               enrollment_hash=user.biometric_face_hash, expires_at=now + timedelta(seconds=45),
                               consumed_at=now, checks={key: True for key in EvaluationCalibrationService.REQUIRED_CHECKS}))
    for index in range(count):
        db.add(TheoryQuestion(skill_id=offer.skill_id, level_number=1, status="PUBLISHED",
                              content={**complete(), "prompt": f"Explain mutability {index}"}))
    await db.commit()


@pytest.mark.asyncio
async def test_new_start_requires_explicit_text_consent_without_consuming_attempt(scenario):
    client, db, user, offer = scenario
    evaluation_id = (await client.post(endpoint(offer, "consent"), json=CONSENT)).json()["data"]["id"]
    await prepare(db, user, offer, evaluation_id)
    response = await client.post("/api/evaluations/start", json={"evaluation_id": evaluation_id, "level_number": 1})
    assert response.status_code == 400
    assert response.json() == {"statuscode": 400, "message": "Se requiere consentimiento explícito para enviar texto de respuesta al corrector externo.", "data": None}
    state = (await client.get(endpoint(offer, "preflight"))).json()["data"]
    assert state["attempts_used"] == 0 and state["free_evaluations_left"] == 3
    assert state["pending_evaluation_id"] == evaluation_id


@pytest.mark.asyncio
async def test_unconfigured_provider_does_not_consume_attempt(scenario, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "THEORY_GRADING_PROVIDER", "disabled")
    client, db, user, offer = scenario
    evaluation_id = (await client.post(endpoint(offer, "consent"), json=CONSENT)).json()["data"]["id"]
    await prepare(db, user, offer, evaluation_id)
    response = await client.post("/api/evaluations/start", json={"evaluation_id": evaluation_id, "level_number": 1, "text_grading_consent": True})
    assert response.status_code == 503
    assert response.json() == {"statuscode": 503, "message": "El corrector teórico no está configurado. Tu intento no se descontó.", "data": None}
    state = (await client.get(endpoint(offer, "preflight"))).json()["data"]
    assert state["attempts_used"] == 0 and state["free_evaluations_left"] == 3


@pytest.mark.asyncio
async def test_start_is_idempotent_and_never_exposes_correction_keys(scenario):
    client, db, user, offer = scenario
    consent = await client.post(endpoint(offer, "consent"), json=CONSENT)
    evaluation_id = consent.json()["data"]["id"]
    await prepare(db, user, offer, evaluation_id)
    payload = {"evaluation_id": evaluation_id, "level_number": 1, "text_grading_consent": True}
    first = await client.post("/api/evaluations/start", json=payload)
    assert first.status_code == 200
    body = first.json()
    assert body["message"] == "Examen teórico iniciado. Tu intento quedó registrado."
    data = body["data"]
    assert data["evaluation_id"] == evaluation_id and data["status"] == "THEORY_ACTIVE"
    assert data["level_number"] == 1 and data["question_count"] == 5
    assert data["started_at"] and data["deadline_at"]
    again = await client.post("/api/evaluations/start", json=payload)
    assert again.status_code == 200 and again.json() == body
    questions = await client.get(f"/api/evaluations/{evaluation_id}/questions")
    assert questions.status_code == 200
    assert questions.json()["count"] == 5
    items = questions.json()["data"]
    assert len({item["id"] for item in items}) == 5
    for item in items:
        assert set(item) == {"id", "version", "position", "kind", "prompt", "choices", "time_limit_seconds", "max_score"}
    blocked = await client.get(endpoint(offer, "preflight"))
    assert blocked.status_code == 403
    assert blocked.json() == {"statuscode": 403, "message": "Límite de evaluaciones gratuitas alcanzado para esta habilidad", "data": None}


@pytest.mark.asyncio
@pytest.mark.parametrize("condition", ["calibration", "bank", "enrollment"])
async def test_rejected_start_preserves_consent_and_free_attempt(scenario, condition):
    client, db, user, offer = scenario
    consent = (await client.post(endpoint(offer, "consent"), json=CONSENT)).json()["data"]
    await prepare(db, user, offer, consent["id"], count=4 if condition == "bank" else 5)
    if condition == "calibration":
        evaluation = await db.get(Evaluation, uuid.UUID(consent["id"]))
        evaluation.status = "PENDING_CALIBRATION"
    if condition == "enrollment":
        user.biometric_face_hash = "replaced-face"
    await db.commit()
    rejected = await client.post("/api/evaluations/start", json={"evaluation_id": consent["id"], "level_number": 1, "text_grading_consent": True})
    message = ("No hay suficientes preguntas publicadas para esta habilidad y nivel." if condition == "bank"
               else "Completá una calibración válida antes de iniciar el examen.")
    assert rejected.status_code == 409
    assert rejected.json() == {"statuscode": 409, "message": message, "data": None}
    check = await client.get(endpoint(offer, "preflight"))
    assert check.status_code == 200
    state = check.json()["data"]
    assert state["free_evaluations_left"] == 3 and state["attempts_used"] == 0
    assert state["pending_evaluation_id"] == consent["id"]


@pytest.mark.asyncio
async def test_other_members_and_admins_cannot_start_or_read_foreign_exam(scenario):
    from app.models import User, UserRole
    from app.core.security import create_access_token
    client, db, user, offer = scenario
    consent = (await client.post(endpoint(offer, "consent"), json=CONSENT)).json()["data"]
    await prepare(db, user, offer, consent["id"])
    owner_auth = client.headers["Authorization"]
    for role in [UserRole.MEMBER, UserRole.ADMIN]:
        stranger = User(email=f"{uuid.uuid4()}@example.test", full_name="Stranger", role=role)
        db.add(stranger)
        await db.commit()
        client.headers["Authorization"] = f"Bearer {create_access_token(subject=str(stranger.id), role=role.value)}"
        for response in [await client.post("/api/evaluations/start", json={"evaluation_id": consent["id"], "level_number": 1, "text_grading_consent": True}),
                         await client.get(f"/api/evaluations/{consent['id']}/questions"),
                         await client.get(f"/api/evaluations/{consent['id']}/result"),
                         await client.post(f"/api/evaluations/{consent['id']}/grading/retry", json={})]:
            assert response.status_code == 404
            assert response.json() == {"statuscode": 404, "message": "Recurso no encontrado", "data": None}
    client.headers["Authorization"] = owner_auth
    check = (await client.get(endpoint(offer, "preflight"))).json()["data"]
    assert check["free_evaluations_left"] == 3 and check["attempts_used"] == 0


@pytest.mark.asyncio
async def test_assigned_snapshots_survive_bank_archival_and_level_change_is_rejected(scenario):
    from app.models import User, UserRole
    from app.core.security import create_access_token
    client, db, user, offer = scenario
    consent = (await client.post(endpoint(offer, "consent"), json=CONSENT)).json()["data"]
    await prepare(db, user, offer, consent["id"])
    payload = {"evaluation_id": consent["id"], "level_number": 1, "text_grading_consent": True}
    started = await client.post("/api/evaluations/start", json=payload)
    assert started.status_code == 200
    path = f"/api/evaluations/{consent['id']}/questions"
    before = (await client.get(path)).json()
    conflict = await client.post("/api/evaluations/start", json={**payload, "level_number": 2})
    assert conflict.status_code == 409
    assert conflict.json() == {"statuscode": 409, "message": "El examen ya comenzó con otro nivel.", "data": None}
    owner_auth = client.headers["Authorization"]
    admin = User(email=f"{uuid.uuid4()}@example.test", full_name="Admin", role=UserRole.ADMIN)
    db.add(admin)
    await db.commit()
    client.headers["Authorization"] = f"Bearer {create_access_token(subject=str(admin.id), role='ADMIN')}"
    for item in before["data"]:
        archived = await client.post(f"/api/admin/theory/questions/{item['id']}/archive", json={"expected_version": 1})
        assert archived.status_code == 200 and archived.json()["data"]["version"] == 2
    client.headers["Authorization"] = owner_auth
    assert (await client.get(path)).json() == before
    replay = await client.post("/api/evaluations/start", json=payload)
    assert replay.status_code == 200 and replay.json() == started.json()


@pytest.mark.asyncio
async def test_missing_speech_assets_never_consume_an_attempt(scenario, monkeypatch, tmp_path):
    from app.services.local_speech_service import LocalSpeechService
    from app.services.theory_exam_service import TheoryExamService
    monkeypatch.setattr(LocalSpeechService, "MODEL_DIR", tmp_path)
    monkeypatch.setattr(TheoryExamService, "check_runtime", staticmethod(LocalSpeechService.ensure_available))
    client, db, user, offer = scenario
    key = (await client.post(endpoint(offer, "consent"), json=CONSENT)).json()["data"]["id"]
    await prepare(db, user, offer, key)
    response = await client.post("/api/evaluations/start", json={"evaluation_id": key, "level_number": 1, "text_grading_consent": True})
    assert response.status_code == 503
    assert response.json() == {"statuscode": 503, "message": LocalSpeechService.UNAVAILABLE, "data": None}
    before = (await client.get(endpoint(offer, "preflight"))).json()["data"]
    assert before["free_evaluations_left"] == 3 and before["attempts_used"] == 0
