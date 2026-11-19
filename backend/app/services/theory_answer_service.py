"""Server-timed oral submissions; raw audio remains transient."""
import asyncio
import base64
import binascii
import hashlib
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone

from starlette.concurrency import run_in_threadpool

from app.core.exceptions import SkillMatchException
from app.models.theory_exam import TheoryExam
from app.schemas.theory_exam import OralAnswerResponse, PublicTheoryQuestion, TheoryProgressResponse
from app.services.local_speech_service import LocalSpeechService
from app.services.theory_exam_service import TheoryExamService


class TheoryAnswerService:
    @staticmethod
    def deadline(exam):
        if exam.current_position >= len(exam.questions):
            return None
        opened = exam.question_started_at or exam.started_at
        return min(opened + timedelta(seconds=exam.questions[exam.current_position]["time_limit_seconds"]),
                   exam.deadline_at)

    @classmethod
    def expire(cls, exam, evaluation, now):
        while exam.current_position < len(exam.questions):
            deadline = cls.deadline(exam)
            if now < deadline:
                break
            question = exam.questions[exam.current_position]
            exam.answers = [*exam.answers, {"question_id": question["id"], "status": "TIMED_OUT"}]
            exam.current_position += 1
            exam.question_started_at = deadline
        if exam.current_position == len(exam.questions):
            evaluation.status = "THEORY_PENDING_REVIEW" if exam.grading_state not in {"GRADING", "COMPLETE", "ERROR"} else evaluation.status
            if exam.grading_state not in {"GRADING", "COMPLETE", "ERROR"}:
                exam.grading_state = "PENDING"

    @classmethod
    async def locked(cls, db, user, key):
        evaluation = await TheoryExamService.owned(db, user, key, lock=True)
        exam = await db.get(TheoryExam, key, populate_existing=True)
        if exam is None:
            raise SkillMatchException(statuscode=409, message="El examen teórico todavía no comenzó.")
        return evaluation, exam

    @classmethod
    async def status(cls, db, user, key):
        evaluation, exam = await cls.locked(db, user, key)
        now = datetime.now(timezone.utc)
        cls.expire(exam, evaluation, now)
        current = exam.questions[exam.current_position] if exam.current_position < len(exam.questions) else None
        result = TheoryProgressResponse(
            evaluation_id=key, status=evaluation.status, question_count=len(exam.questions),
            answered_count=sum(item["status"] == "RECORDED" for item in exam.answers),
            position=min(exam.current_position + 1, len(exam.questions)), server_time=now,
            deadline_at=exam.deadline_at, question_deadline_at=cls.deadline(exam),
            current_question=PublicTheoryQuestion.model_validate(current) if current else None,
            grading_state=exam.grading_state, grading_score=exam.grading_score,
            grading_feedback=exam.grading_result.get("feedback") if exam.grading_result else None,
        )
        await db.commit()
        return result

    @staticmethod
    def replay(exam, payload, digest):
        for item in exam.answers:
            if item.get("submission_id") == str(payload.submission_id):
                if item["digest"] != digest or item["question_id"] != str(payload.question_id):
                    raise SkillMatchException(statuscode=409, message="El identificador de respuesta ya fue usado con otro contenido.")
                return OralAnswerResponse.model_validate(item)
        return None

    @classmethod
    async def submit(cls, db, user, key, payload):
        user = SimpleNamespace(id=user.id, role=user.role)
        evaluation, exam = await cls.locked(db, user, key)
        try:
            raw = base64.b64decode(payload.audio_base64, validate=True)
        except (ValueError, binascii.Error):
            raise SkillMatchException(statuscode=400, message="El audio de respuesta no es válido.")
        digest = hashlib.sha256(raw).hexdigest()
        existing = cls.replay(exam, payload, digest)
        if existing is not None:
            return existing
        received_at = datetime.now(timezone.utc)
        cls.expire(exam, evaluation, received_at)
        if exam.current_position >= len(exam.questions):
            await db.commit()
            raise SkillMatchException(statuscode=410, message="El tiempo para responder terminó.")
        current = exam.questions[exam.current_position]
        if current["id"] != str(payload.question_id):
            await db.commit()
            raise SkillMatchException(statuscode=409, message="La pregunta ya no está activa.")
        # Do not retain a database row lock while local inference is running.
        await db.rollback()
        try:
            transcript = await asyncio.wait_for(run_in_threadpool(LocalSpeechService.transcribe, raw), timeout=60)
        except TimeoutError:
            # A native thread may finish later, but only this coroutine can persist answers.
            raise SkillMatchException(statuscode=503, message=LocalSpeechService.UNAVAILABLE)
        if not isinstance(transcript, str) or not transcript.strip() or len(transcript) > 16000:
            raise SkillMatchException(statuscode=503, message="No se pudo transcribir la respuesta de manera válida.")
        evaluation, exam = await cls.locked(db, user, key)
        existing = cls.replay(exam, payload, digest)
        if existing is not None:
            return existing
        if exam.current_position >= len(exam.questions) or exam.questions[exam.current_position]["id"] != str(payload.question_id):
            raise SkillMatchException(statuscode=409, message="La pregunta ya no está activa.")
        answer = {"submission_id": str(payload.submission_id), "question_id": str(payload.question_id),
                  "transcript": transcript.strip(), "received_at": received_at.isoformat(),
                  "status": "RECORDED", "digest": digest}
        exam.answers = [*exam.answers, answer]
        exam.current_position += 1
        exam.question_started_at = datetime.now(timezone.utc)
        if exam.current_position == len(exam.questions):
            evaluation.status = "THEORY_PENDING_REVIEW"
            exam.grading_state = "PENDING"
        await db.commit()
        return OralAnswerResponse.model_validate(answer)
