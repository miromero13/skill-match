import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from starlette.concurrency import run_in_threadpool

from app.core.exceptions import SkillMatchException
from app.models.calibration import CalibrationChallenge
from app.models.evaluation import Evaluation
from app.models.user import UserRole
from app.schemas.calibration import CalibrationStateResponse
from app.services.calibration_vision_service import CalibrationVisionService
from app.services.integrity import messages
from app.services.integrity.calibration import REQUIRED_CHECKS


class EvaluationCalibrationService:
    # Every check of the engine's calibration (camera, faces, identity, pose, gaze zone, silence, speech, voice, ...).
    REQUIRED_CHECKS = REQUIRED_CHECKS

    @staticmethod
    async def owned(db, user, evaluation_id, *, lock=False):
        statement = select(Evaluation).where(Evaluation.id == evaluation_id, Evaluation.user_id == user.id)
        if lock:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        evaluation = await db.scalar(statement)
        if evaluation is None:
            raise SkillMatchException(statuscode=404, message="Recurso no encontrado")
        if user.role != UserRole.MEMBER:
            raise SkillMatchException(statuscode=403, message="La evaluación requiere una cuenta de miembro")
        if not evaluation.biometric_consent_at:
            raise SkillMatchException(statuscode=400, message="Debés aceptar el consentimiento antes de activar los periféricos.")
        if not (user.biometric_embedding and user.biometric_face_hash):
            raise SkillMatchException(statuscode=400, message="Debés registrar tu rostro testigo antes de la calibración.")
        if evaluation.started_at is not None or evaluation.status not in ("PENDING_CALIBRATION", "READY_FOR_THEORY"):
            raise SkillMatchException(statuscode=409, message="Esta evaluación no admite una nueva calibración.")
        return evaluation

    @classmethod
    async def challenge(cls, db, user, evaluation_id):
        evaluation = await cls.owned(db, user, evaluation_id, lock=True)
        now = datetime.now(timezone.utc)
        await db.execute(update(CalibrationChallenge).where(
            CalibrationChallenge.evaluation_id == evaluation.id,
            CalibrationChallenge.consumed_at.is_(None),
        ).values(consumed_at=now))
        challenge = CalibrationChallenge(
            evaluation_id=evaluation.id, action=secrets.choice(("TURN_LEFT", "TURN_RIGHT")),
            enrollment_hash=user.biometric_face_hash, expires_at=now + timedelta(seconds=45),
        )
        evaluation.status = "PENDING_CALIBRATION"
        db.add(challenge)
        await db.commit()
        await db.refresh(challenge)
        return challenge

    @classmethod
    async def state(cls, db, user, evaluation_id):
        evaluation = await cls.owned(db, user, evaluation_id)
        latest = await db.scalar(select(CalibrationChallenge).where(
            CalibrationChallenge.evaluation_id == evaluation_id,
        ).order_by(CalibrationChallenge.created_at.desc(), CalibrationChallenge.id.desc()).limit(1))
        enrollment_matches = latest is not None and latest.enrollment_hash == user.biometric_face_hash
        checks = latest.checks if enrollment_matches and latest.checks else {}
        # Ready needs every check AND the three things supervision is seeded with: no clean pass by omission.
        complete = latest is not None and all(
            value is not None for value in (latest.gaze_zone, latest.voiceprint, latest.occlusion_ref))
        ready = (evaluation.status == "READY_FOR_THEORY" and complete
                 and set(checks) == cls.REQUIRED_CHECKS and all(value is True for value in checks.values()))
        return CalibrationStateResponse(
            evaluation_id=evaluation.id, ready=ready,
            status="READY_FOR_THEORY" if ready else "PENDING_CALIBRATION",
            started_at=evaluation.started_at, checks=checks,
        )

    @classmethod
    async def verify(cls, db, user, evaluation_id, payload):
        evaluation = await cls.owned(db, user, evaluation_id, lock=True)
        challenge = await db.get(CalibrationChallenge, payload.challenge_id)
        if challenge is None or challenge.evaluation_id != evaluation.id:
            raise SkillMatchException(statuscode=404, message="Recurso no encontrado")
        if challenge.consumed_at is not None:
            raise SkillMatchException(statuscode=409, message="El reto ya fue utilizado. Solicitá uno nuevo.")
        if challenge.expires_at <= datetime.now(timezone.utc):
            raise SkillMatchException(statuscode=410, message="El reto venció. Solicitá uno nuevo; tu intento no se descontó.")
        if challenge.enrollment_hash != user.biometric_face_hash:
            raise SkillMatchException(statuscode=409, message="Tu enrolamiento cambió. Solicitá un nuevo reto.")
        output = await run_in_threadpool(
            CalibrationVisionService.assess, payload, challenge.action, user.biometric_embedding)
        checks = output.checks
        if set(checks) != cls.REQUIRED_CHECKS or not all(value is True for value in checks.values()):
            raise SkillMatchException(statuscode=400, message=messages.INCOMPLETE)
        challenge.consumed_at = datetime.now(timezone.utc)
        challenge.checks = checks
        challenge.gaze_zone = output.gaze_zone.to_dict()
        challenge.voiceprint = output.voiceprint
        challenge.occlusion_ref = output.occlusion_ref
        evaluation.status = "READY_FOR_THEORY"
        await db.commit()
        return await cls.state(db, user, evaluation_id)
