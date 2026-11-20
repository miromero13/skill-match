"""Field-testing calibration skip: only behind EVALUATION_CALIBRATION_SKIP_ENABLED (default off)."""
import uuid

import pytest
from pydantic import SecretStr
from sqlalchemy import func, select

from tests.test_evaluation_preflight import CONSENT, endpoint, isolated_db, scenario  # noqa: F401
from app.core.config import settings
from app.core.security import create_access_token
from app.models import CalibrationChallenge, Evaluation, SkillLevel, User, UserRole
from app.models.theory_question import TheoryQuestion
from app.services.evaluation_calibration_service import EvaluationCalibrationService

SKIP_MESSAGE = "Calibración omitida para pruebas. El examen todavía no comenzó."


def skip_url(evaluation_id):
    return f"/api/evaluations/{evaluation_id}/calibration/skip"


async def consented(client, offer):
    response = await client.post(endpoint(offer, "consent"), json=CONSENT)
    assert response.status_code == 200
    return response.json()["data"]["id"]


async def challenge_count(db, evaluation_id):
    return await db.scalar(select(func.count()).select_from(CalibrationChallenge).where(
        CalibrationChallenge.evaluation_id == uuid.UUID(evaluation_id)))


@pytest.mark.asyncio
async def test_flag_off_skip_is_hidden_and_changes_nothing(scenario, monkeypatch):
    monkeypatch.setattr(settings, "EVALUATION_CALIBRATION_SKIP_ENABLED", False)
    client, db, _, offer = scenario
    evaluation_id = await consented(client, offer)
    response = await client.post(skip_url(evaluation_id))
    assert response.status_code == 404
    assert response.json() == {"statuscode": 404, "message": "Recurso no encontrado", "data": None}
    evaluation = await db.get(Evaluation, uuid.UUID(evaluation_id))
    await db.refresh(evaluation)
    assert evaluation.status == "PENDING_CALIBRATION" and evaluation.started_at is None
    state = (await client.get(f"/api/evaluations/{evaluation_id}/environment/verify")).json()["data"]
    assert state["ready"] is False and state["skipped"] is False


@pytest.mark.asyncio
async def test_flag_off_status_alone_is_not_ready(scenario, monkeypatch):
    monkeypatch.setattr(settings, "EVALUATION_CALIBRATION_SKIP_ENABLED", False)
    client, db, _, offer = scenario
    evaluation_id = await consented(client, offer)
    evaluation = await db.get(Evaluation, uuid.UUID(evaluation_id))
    evaluation.status = "READY_FOR_THEORY"
    await db.commit()
    state = (await client.get(f"/api/evaluations/{evaluation_id}/environment/verify")).json()["data"]
    assert state["ready"] is False and state["skipped"] is False


@pytest.mark.asyncio
async def test_flag_on_skip_marks_ready_without_fake_calibration(scenario, monkeypatch):
    monkeypatch.setattr(settings, "EVALUATION_CALIBRATION_SKIP_ENABLED", True)
    client, db, user, offer = scenario
    evaluation_id = await consented(client, offer)
    response = await client.post(skip_url(evaluation_id))
    assert response.status_code == 200
    body = response.json()
    assert body["statuscode"] == 200 and body["message"] == SKIP_MESSAGE
    data = body["data"]
    assert data["ready"] is True and data["skipped"] is True and data["checks"] == {}
    assert data["status"] == "READY_FOR_THEORY" and data["started_at"] is None
    evaluation = await db.get(Evaluation, uuid.UUID(evaluation_id))
    await db.refresh(evaluation)
    assert evaluation.status == "READY_FOR_THEORY" and evaluation.started_at is None
    assert await challenge_count(db, evaluation_id) == 0
    assert await EvaluationCalibrationService.valid_seed(db, user) is None
    state = (await client.get(f"/api/evaluations/{evaluation_id}/environment/verify")).json()["data"]
    assert state["ready"] is True and state["skipped"] is True
    quota = (await client.get(endpoint(offer, "preflight"))).json()["data"]
    assert quota["free_evaluations_left"] == 3 and quota["attempts_used"] == 0


@pytest.mark.asyncio
async def test_flag_on_foreign_evaluation_is_hidden(scenario, monkeypatch):
    monkeypatch.setattr(settings, "EVALUATION_CALIBRATION_SKIP_ENABLED", True)
    client, db, _, offer = scenario
    evaluation_id = await consented(client, offer)
    other = User(email=f"{uuid.uuid4()}@example.test", full_name="Other", role=UserRole.MEMBER,
                 biometric_embedding="[0.1]", biometric_face_hash="other-reference")
    db.add(other)
    await db.commit()
    client.headers["Authorization"] = f"Bearer {create_access_token(subject=str(other.id), role='MEMBER')}"
    response = await client.post(skip_url(evaluation_id))
    assert response.status_code == 404
    assert response.json() == {"statuscode": 404, "message": "Recurso no encontrado", "data": None}
    evaluation = await db.get(Evaluation, uuid.UUID(evaluation_id))
    await db.refresh(evaluation)
    assert evaluation.status == "PENDING_CALIBRATION"


@pytest.mark.asyncio
@pytest.mark.parametrize("flag", [False, True])
async def test_preflight_exposes_skip_flag(scenario, monkeypatch, flag):
    monkeypatch.setattr(settings, "EVALUATION_CALIBRATION_SKIP_ENABLED", flag)
    client, _, _, offer = scenario
    data = (await client.get(endpoint(offer, "preflight"))).json()["data"]
    assert data["calibration_skip_allowed"] is flag


@pytest.mark.asyncio
async def test_theory_exam_starts_after_skip(scenario, monkeypatch):
    from tests.test_theory_question_publication import complete
    from app.services.theory_exam_service import TheoryExamService
    monkeypatch.setattr(settings, "EVALUATION_CALIBRATION_SKIP_ENABLED", True)
    monkeypatch.setattr(TheoryExamService, "check_runtime", staticmethod(lambda: None))
    monkeypatch.setattr(settings, "THEORY_GRADING_PROVIDER", "openai")
    monkeypatch.setattr(settings, "THEORY_GRADING_MODEL", "mock-model")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", SecretStr("mock-key"))
    client, db, _, offer = scenario
    evaluation_id = await consented(client, offer)
    db.add(SkillLevel(skill_id=offer.skill_id, level_number=1, name="Principiante"))
    for index in range(5):
        db.add(TheoryQuestion(skill_id=offer.skill_id, level_number=1, status="PUBLISHED",
                              content={**complete(), "prompt": f"Explain mutability {index}"}))
    await db.commit()
    assert (await client.post(skip_url(evaluation_id))).status_code == 200
    response = await client.post("/api/evaluations/start", json={
        "evaluation_id": evaluation_id, "level_number": 1, "text_grading_consent": True})
    assert response.status_code == 200
    assert response.json()["message"] == "Examen teórico iniciado. Tu intento quedó registrado."
