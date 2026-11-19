"""Serialize actual starts per member; preparation never reserves an attempt."""
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, select

from app.core.exceptions import SkillMatchException
from app.models.evaluation import Evaluation
from app.models.theory_exam import TheoryExam
from app.models.theory_question import TheoryQuestion
from app.models.user import User, UserRole
from app.schemas.theory_exam import TheoryStartResponse, PublicTheoryQuestion
from app.services.evaluation_calibration_service import EvaluationCalibrationService
from app.services.evaluation_preflight_service import (
    EvaluationPreflightService,
    POLICY_VERSION,
    resolve_declared_level,
)
from app.services.local_speech_service import LocalSpeechService
from app.services.theory_grading_provider import PROMPT_VERSION, provider_configuration


class TheoryExamService:
    QUESTION_COUNT = 5
    check_runtime = staticmethod(LocalSpeechService.ensure_available)

    @staticmethod
    async def owned(db, user, evaluation_id, *, lock=False):
        query = select(Evaluation).where(Evaluation.id == evaluation_id, Evaluation.user_id == user.id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        evaluation = await db.scalar(query)
        if evaluation is None or user.role != UserRole.MEMBER:
            raise SkillMatchException(statuscode=404, message="Recurso no encontrado")
        return evaluation

    @staticmethod
    def response(evaluation, exam):
        return TheoryStartResponse(evaluation_id=evaluation.id, level_number=exam.level_number,
                                   status=evaluation.status, question_count=len(exam.questions),
                                   started_at=exam.started_at, deadline_at=exam.deadline_at)

    @classmethod
    async def start(cls, db, user, payload):
        # Consent and start use the same per-member lock, including cross-skill quota races.
        user = await db.scalar(select(User).where(User.id == user.id).with_for_update()
                               .execution_options(populate_existing=True))
        evaluation = await cls.owned(db, user, payload.evaluation_id, lock=True)
        existing = await db.get(TheoryExam, evaluation.id)
        if existing is not None:
            if payload.level_number is not None and existing.level_number != payload.level_number:
                raise SkillMatchException(statuscode=409, message="El examen ya comenzó con otro nivel.")
            return cls.response(evaluation, existing)
        if not payload.text_grading_consent:
            raise SkillMatchException(statuscode=400, message="Se requiere consentimiento explícito para enviar texto de respuesta al corrector externo.")
        configured = provider_configuration()
        if configured is None:
            raise SkillMatchException(statuscode=503, message="El corrector teórico no está configurado. Tu intento no se descontó.")
        offer, *_ = await EvaluationPreflightService.context(db, user, evaluation.teaching_skill_id)
        target_level = payload.level_number
        if target_level is None:
            target_level, _ = resolve_declared_level(offer.declared_level)
        state = await EvaluationCalibrationService.state(db, user, evaluation.id)
        if not state.ready or evaluation.policy_version != POLICY_VERSION:
            raise SkillMatchException(statuscode=409, message="Completá una calibración válida antes de iniciar el examen.")
        latest = select(TheoryQuestion.id, func.max(TheoryQuestion.version).label("version")).group_by(
            TheoryQuestion.id).subquery()
        candidates = (await db.scalars(select(TheoryQuestion).join(latest, and_(
            TheoryQuestion.id == latest.c.id, TheoryQuestion.version == latest.c.version,
        )).where(TheoryQuestion.skill_id == evaluation.skill_id,
                 TheoryQuestion.level_number == target_level,
                 TheoryQuestion.status == "PUBLISHED"))).all()
        if len(candidates) < cls.QUESTION_COUNT:
            raise SkillMatchException(statuscode=409, message="No hay suficientes preguntas publicadas para esta habilidad y nivel.")
        cls.check_runtime()
        selected = secrets.SystemRandom().sample(candidates, cls.QUESTION_COUNT)
        now = datetime.now(timezone.utc)
        # Keep correction material server-side in the fixed snapshot, never in public schemas.
        questions = [{"id": str(item.id), "version": item.version, "position": index + 1,
                      **{key: item.content[key] for key in ("kind", "prompt", "choices", "reference_answer",
                          "criteria", "time_limit_seconds", "max_score")}} for index, item in enumerate(selected)]
        exam = TheoryExam(evaluation_id=evaluation.id, level_number=target_level,
                          started_at=now, deadline_at=now + timedelta(minutes=10), questions=questions,
                          current_position=0, question_started_at=now, answers=[], text_consent_at=now,
                          grading_provider=configured[0], grading_model=configured[1],
                          grading_prompt_version=PROMPT_VERSION, grading_state="PENDING")
        evaluation.started_at = now
        evaluation.status = "THEORY_ACTIVE"
        db.add(exam)
        await db.commit()
        return cls.response(evaluation, exam)

    @classmethod
    async def questions(cls, db, user, evaluation_id):
        await cls.owned(db, user, evaluation_id)
        exam = await db.get(TheoryExam, evaluation_id)
        if exam is None:
            raise SkillMatchException(statuscode=409, message="El examen teórico todavía no comenzó.")
        return [PublicTheoryQuestion.model_validate(item) for item in exam.questions]
