"""Persist rubric grading without holding database locks across provider I/O."""
from app.core.config import settings
from app.core.exceptions import SkillMatchException
from app.models.theory_exam import TheoryExam
from app.schemas.theory_exam import TheoryGradingResponse
from app.services.theory_exam_service import TheoryExamService
from app.services.theory_answer_service import TheoryAnswerService
from app.services.theory_grading_provider import PROMPT_VERSION, TheoryGradingProvider, provider_configuration


ERROR_MESSAGE = "No se pudo corregir la evaluación. Tu respuesta y tu intento permanecen guardados; podés reintentar."


class TheoryGradingService:
    @staticmethod
    def response(key, exam):
        return TheoryGradingResponse(evaluation_id=key, state=exam.grading_state,
            score=exam.grading_score, max_score=sum(float(q["max_score"]) for q in exam.questions),
            feedback=exam.grading_result.get("feedback") if exam.grading_result else None,
            provider=exam.grading_provider, model=exam.grading_model,
            prompt_version=exam.grading_prompt_version)

    @classmethod
    async def result(cls, db, user, key):
        await TheoryExamService.owned(db, user, key)
        exam = await db.get(TheoryExam, key)
        if exam is None:
            raise SkillMatchException(statuscode=409, message="El examen teórico todavía no comenzó.")
        return cls.response(key, exam)

    @classmethod
    async def retry(cls, db, user, key):
        evaluation, exam = await TheoryAnswerService.locked(db, user, key)
        if exam.grading_state == "COMPLETE":
            return cls.response(key, exam)
        if not exam.text_consent_at or exam.grading_provider not in {"openai", "gemini"} or not exam.grading_model:
            raise SkillMatchException(statuscode=409, message="No existe consentimiento y configuración fijada para corregir este examen.")
        if evaluation.status not in {
            "THEORY_PENDING_REVIEW",
            "THEORY_GRADED",
            "THEORY_GRADING_ERROR",
            "CODE_DEFENSE_PENDING",
            "READY_FOR_FINAL_REVIEW",
        }:
            raise SkillMatchException(statuscode=409, message="El examen todavía no está listo para corrección.")
        config = provider_configuration()
        if not config or config[:2] != (exam.grading_provider, exam.grading_model):
            raise SkillMatchException(statuscode=503, message="La configuración fijada del corrector no está disponible.")
        if exam.grading_state == "GRADING":
            raise SkillMatchException(statuscode=409, message="La corrección ya está en curso.")
        exam.grading_state, exam.grading_error = "GRADING", None
        evaluation.status = "THEORY_GRADING"
        await db.commit()
        try:
            provider = TheoryGradingProvider(provider=exam.grading_provider, model=exam.grading_model,
                api_key=config[2], timeout=settings.THEORY_GRADING_TIMEOUT_SECONDS)
            feedback, score = [], 0.0
            for answer in exam.answers:
                question = next((item for item in exam.questions if item["id"] == answer.get("question_id")), None)
                if question is None or answer.get("status") != "RECORDED":
                    continue
                criteria = question.get("criteria", [])
                rubric = [{"criterion": item["name"], "weight": item["weight"], "description": item["description"]}
                          for item in criteria]
                grade = await provider.grade(question=question["prompt"], reference=question["reference_answer"],
                    transcript=answer["transcript"], rubric=rubric)
                by_name = {item.criterion: item for item in grade.criteria}
                points = float(question["max_score"]) * sum(float(item["weight"]) * by_name[item["name"]].attainment
                    for item in criteria) / 100
                score += points
                feedback.append({"question_id": question["id"], "question_version": question["version"],
                    "points": round(points, 4), "max_score": question["max_score"], "feedback": grade.feedback,
                    "criteria": [{"name": item["name"], "weight": item["weight"],
                        "attainment": by_name[item["name"]].attainment, "reason": by_name[item["name"]].reason}
                        for item in criteria]})
            final_score = round(score, 4)
            evaluation, exam = await TheoryAnswerService.locked(db, user, key)
            if exam is None or exam.grading_state != "GRADING" or not exam.text_consent_at:
                raise SkillMatchException(statuscode=409, message="El estado del examen cambió durante la corrección.")
            exam.grading_result = {"feedback": feedback}
            exam.grading_score = final_score
            exam.grading_state = "COMPLETE"
            exam.grading_error = None
            evaluation.status = "THEORY_GRADED"
            await db.commit()
            return cls.response(key, exam)
        except SkillMatchException:
            raise
        except Exception as exc:
            # Never expose provider payloads, keys, response bodies, or exception text.
            evaluation, exam = await TheoryAnswerService.locked(db, user, key)
            if exam is not None and exam.grading_state == "GRADING":
                exam.grading_state, exam.grading_error = "ERROR", "PROVIDER_FAILURE"
                evaluation.status = "THEORY_GRADING_ERROR"
                await db.commit()
            raise SkillMatchException(statuscode=503, message=ERROR_MESSAGE) from exc
