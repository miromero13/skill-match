import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select, update
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.exceptions import SkillMatchException
from app.models.calibration import CalibrationChallenge
from app.models.evaluation import Evaluation
from app.models.user import UserRole
from app.schemas.calibration import CalibrationStateResponse
from app.services.calibration_vision_service import CalibrationVisionService
from app.services.integrity import messages, thresholds as t, voiceprint as vp
from app.services.integrity.calibration import REQUIRED_CHECKS
from app.services.integrity.models import GazeZone


@dataclass(frozen=True)
class CalibrationSeed:
    """What a valid calibration gives a supervision trial. Server-side only: it is never serialized into a response."""

    gaze_zone: GazeZone
    voiceprint: dict[str, Any]
    ambient_rms: Optional[float]  # the noise floor measured in the silent step (also inside ``voiceprint``)
    occlusion_ref: dict[str, float]


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
            bool(value) for value in (latest.gaze_zone, latest.voiceprint, latest.occlusion_ref))
        ready = (evaluation.status == "READY_FOR_THEORY" and complete
                 and set(checks) == cls.REQUIRED_CHECKS and all(value is True for value in checks.values()))
        # Field-testing skip: only while the flag is on; it never produces a seed (valid_seed ignores it).
        skipped = (not ready and settings.EVALUATION_CALIBRATION_SKIP_ENABLED
                   and evaluation.status == "READY_FOR_THEORY")
        ready = ready or skipped
        return CalibrationStateResponse(
            evaluation_id=evaluation.id, ready=ready, skipped=skipped,
            status="READY_FOR_THEORY" if ready else "PENDING_CALIBRATION",
            started_at=evaluation.started_at, checks={} if skipped else checks,
        )

    @classmethod
    async def skip(cls, db, user, evaluation_id):
        if not settings.EVALUATION_CALIBRATION_SKIP_ENABLED:
            raise SkillMatchException(statuscode=404, message="Recurso no encontrado")
        evaluation = await cls.owned(db, user, evaluation_id, lock=True)
        evaluation.status = "READY_FOR_THEORY"
        await db.commit()
        return await cls.state(db, user, evaluation_id)

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

    @classmethod
    async def valid_seed(cls, db, user, now: Optional[datetime] = None) -> Optional[CalibrationSeed]:
        """The zone, voiceprint, ambient floor and occlusion reference of the member's latest valid calibration.

        Valid means: passed every required check, made by this member for the face they are enrolled with now, not
        older than ``CAL_MAX_AGE_HOURS``, with all three inputs stored and readable. Anything else is None (the
        trial then starts unseeded and uses its own calibration endpoints).
        """
        now = now or datetime.now(timezone.utc)
        row = await db.scalar(select(CalibrationChallenge).join(
            Evaluation, Evaluation.id == CalibrationChallenge.evaluation_id,
        ).where(
            Evaluation.user_id == user.id,
            CalibrationChallenge.consumed_at.is_not(None),
            CalibrationChallenge.consumed_at >= now - timedelta(hours=t.CAL_MAX_AGE_HOURS),
            CalibrationChallenge.enrollment_hash == user.biometric_face_hash,
            CalibrationChallenge.gaze_zone.is_not(None),
            CalibrationChallenge.voiceprint.is_not(None),
            CalibrationChallenge.occlusion_ref.is_not(None),
        ).order_by(CalibrationChallenge.consumed_at.desc(), CalibrationChallenge.id.desc()).limit(1))
        if row is None or not user.biometric_face_hash:
            return None
        if not all(isinstance(value, dict) and value for value in (row.gaze_zone, row.voiceprint, row.occlusion_ref)):
            return None  # a JSON null is not a stored input
        checks = row.checks or {}
        if set(checks) != cls.REQUIRED_CHECKS or not all(value is True for value in checks.values()):
            return None
        try:
            zone = GazeZone.from_dict(row.gaze_zone)
            vp.embedding_of(row.voiceprint)
        except (KeyError, TypeError, ValueError, vp.SpeakerModelUnavailable):
            return None
        return CalibrationSeed(zone, dict(row.voiceprint), vp.ambient_rms_of(row.voiceprint), dict(row.occlusion_ref))
