"""Unified finalization and external AI grading across all evaluation modalities."""
from sqlalchemy import select

from app.core.config import settings
from app.core.exceptions import SkillMatchException
from app.models.programming import Challenge, ChallengeSubmission
from app.models.teaching_skill import TeachingSkill
from app.models.theory_exam import TheoryExam
from app.schemas.theory_exam import FinalEvaluationResponse
from app.services.theory_exam_service import TheoryExamService
from app.services.theory_grading_provider import GradingProviderError, TheoryGradingProvider, provider_configuration
from app.services.theory_grading_service import TheoryGradingService

PASSING_SCORE = 70.0

DEFENSE_RUBRIC = [
    {
        "name": "Comprensión de la solución",
        "weight": 50,
        "description": "Explica con claridad qué hace su código, o por qué no logró completarlo.",
    },
    {
        "name": "Justificación técnica y casos borde",
        "weight": 50,
        "description": "Justifica las decisiones tomadas, estructuras usadas o dificultades encontradas.",
    },
]


class EvaluationFinalizationService:
    @classmethod
    async def finalize(cls, db, user, evaluation_id) -> FinalEvaluationResponse:
        evaluation = await TheoryExamService.owned(db, user, evaluation_id)
        if evaluation.status == "CANCELLED":
            raise SkillMatchException(statuscode=409, message="Esta evaluación fue cancelada.")
        if evaluation.status in {"PASSED", "FAILED"} and evaluation.final_summary is not None:
            return FinalEvaluationResponse.model_validate(evaluation.final_summary)

        exam = await db.get(TheoryExam, evaluation.id)
        if exam is None:
            raise SkillMatchException(statuscode=409, message="El examen teórico todavía no comenzó.")

        if exam.grading_state != "COMPLETE":
            await TheoryGradingService.retry(db, user, evaluation.id)
            await db.refresh(exam)
            await db.refresh(evaluation)
            if exam.grading_state != "COMPLETE":
                raise SkillMatchException(
                    statuscode=503,
                    message="No se pudo completar la corrección con la IA externa. Reintentá finalizar.",
                )

        theory_score = float(exam.grading_score or 0.0)
        theory_max = sum(float(q.get("max_score", 0)) for q in exam.questions) or 100.0
        theory_pct = max(0.0, min(100.0, (theory_score / theory_max) * 100.0))
        theory_feedback = exam.grading_result.get("feedback") if exam.grading_result else None

        submission = await db.scalar(
            select(ChallengeSubmission)
            .where(ChallengeSubmission.evaluation_id == evaluation.id)
            .order_by(ChallengeSubmission.submitted_at.desc())
        )

        has_coding = submission is not None
        sandbox_passed = None
        sandbox_total = None
        defense_transcript = None
        defense_score = None
        defense_feedback = None

        if submission is not None:
            if submission.defense_transcript is None:
                raise SkillMatchException(
                    statuscode=409,
                    message="Debés completar la defensa oral del reto antes de finalizar la evaluación.",
                )
            sandbox_passed = submission.passed_tests
            sandbox_total = submission.total_tests
            sandbox_pct = (submission.passed_tests / max(submission.total_tests, 1)) * 100.0
            defense_transcript = submission.defense_transcript

            if submission.defense_score is None:
                config = provider_configuration()
                if not config:
                    raise SkillMatchException(statuscode=503, message="El corrector de IA externa no está configurado.")
                challenge = await db.get(Challenge, submission.challenge_id)
                provider = TheoryGradingProvider(
                    provider=config[0],
                    model=config[1],
                    api_key=config[2],
                    timeout=settings.THEORY_GRADING_TIMEOUT_SECONDS,
                )
                question_ctx = (
                    f"Reto: {challenge.title if challenge else 'Programación'}\n"
                    f"Consigna: {challenge.statement if challenge else ''}\n"
                    f"Tests pasados en sandbox: {submission.passed_tests}/{submission.total_tests}\n"
                    f"Código entregado:\n{submission.code[:4000]}"
                )
                reference_ctx = (
                    "El postulante debe explicar de forma coherente cómo diseñó su solución o "
                    "identificar qué le impidió completarla correctamente."
                )
                try:
                    grade = await provider.grade(
                        question=question_ctx,
                        reference=reference_ctx,
                        transcript=submission.defense_transcript,
                        rubric=DEFENSE_RUBRIC,
                    )
                except GradingProviderError as exc:
                    raise SkillMatchException(
                        statuscode=503,
                        message="No se pudo evaluar la defensa oral con la IA externa. Reintentá finalizar.",
                    ) from exc

                weights = {item["name"]: item["weight"] for item in DEFENSE_RUBRIC}
                computed = sum(
                    weights.get(item.criterion, 0) * item.attainment for item in grade.criteria
                )
                submission.defense_score = round(max(0.0, min(100.0, computed)), 2)
                submission.defense_feedback = grade.feedback

            defense_score = float(submission.defense_score or 0.0)
            defense_feedback = submission.defense_feedback
            final_score = round(0.40 * theory_pct + 0.40 * sandbox_pct + 0.20 * defense_score, 2)
        else:
            final_score = round(theory_pct, 2)

        passed = final_score >= PASSING_SCORE
        skill_validated = False
        if passed and evaluation.teaching_skill_id is not None:
            teaching_skill = await db.get(TeachingSkill, evaluation.teaching_skill_id)
            if teaching_skill is not None:
                teaching_skill.status = "VERIFICADA"
                skill_validated = True

        evaluation.final_score = final_score
        evaluation.status = "PASSED" if passed else "FAILED"
        summary = FinalEvaluationResponse(
            evaluation_id=evaluation.id,
            status=evaluation.status,
            passed=passed,
            final_score=final_score,
            theory_score=round(theory_score, 2),
            theory_max_score=round(theory_max, 2),
            theory_feedback=theory_feedback,
            has_coding_stage=has_coding,
            sandbox_passed_tests=sandbox_passed,
            sandbox_total_tests=sandbox_total,
            defense_transcript=defense_transcript,
            defense_score=defense_score,
            defense_feedback=defense_feedback,
            skill_validated=skill_validated,
        )
        evaluation.final_summary = summary.model_dump(mode="json")
        await db.commit()
        return summary
