"""Shared preparation for all disciplines, without an exam-start bypass."""
from datetime import datetime, timezone

from sqlalchemy import distinct, func, select

from app.core.exceptions import SkillMatchException
from app.models.catalog import Category, Skill
from app.models.evaluation import Evaluation
from app.models.teaching_skill import TeachingSkill
from app.models.user import User, UserRole
from app.schemas.evaluation import EvaluationPreflightResponse

POLICY_VERSION = "v1.0"
FREE_SKILLS = 3
ENROLLMENT_REQUIRED = "Debe registrar su rostro testigo en su perfil antes de solicitar una certificación"
QUOTA_EXHAUSTED = "Límite de evaluaciones gratuitas alcanzado para esta habilidad"


class EvaluationPreflightService:
    @staticmethod
    async def context(db, user, teaching_skill_id, *, lock=False):
        # Serialize consent creation per member, without debiting or reserving a start.
        if lock:
            user = await db.scalar(select(User).where(User.id == user.id).with_for_update())
        result = await db.execute(
            select(TeachingSkill, Skill).join(Skill, TeachingSkill.skill_id == Skill.id)
            .join(Category, Skill.category_id == Category.id)
            .where(TeachingSkill.id == teaching_skill_id, TeachingSkill.user_id == user.id,
                   Skill.is_active.is_(True), Category.is_active.is_(True))
        )
        row = result.first()
        if row is None:
            raise SkillMatchException(statuscode=404, message="Recurso no encontrado")
        if user.role != UserRole.MEMBER:
            raise SkillMatchException(statuscode=403, message="La evaluación requiere una cuenta de miembro")
        if not (user.biometric_embedding and user.biometric_face_hash):
            raise SkillMatchException(statuscode=400, message=ENROLLMENT_REQUIRED)
        offer, skill = row
        attempts_used = await db.scalar(select(func.count()).select_from(Evaluation).where(
            Evaluation.user_id == user.id, Evaluation.skill_id == skill.id,
            Evaluation.started_at.is_not(None),
        ))
        used_skills = await db.scalar(select(func.count(distinct(Evaluation.skill_id))).where(
            Evaluation.user_id == user.id, Evaluation.started_at.is_not(None),
        ))
        if attempts_used or used_skills >= FREE_SKILLS:
            raise SkillMatchException(statuscode=403, message=QUOTA_EXHAUSTED)
        pending = await db.scalar(select(Evaluation).where(
            Evaluation.user_id == user.id, Evaluation.skill_id == skill.id,
        ))
        return offer, skill, pending, FREE_SKILLS - used_skills

    @classmethod
    async def preflight(cls, db, user, teaching_skill_id):
        offer, skill, pending, remaining = await cls.context(db, user, teaching_skill_id)
        return EvaluationPreflightResponse(
            teaching_skill_id=offer.id, skill_name=skill.name,
            syllabus=skill.description or skill.name,
            requirements=["Cámara y micrófono disponibles", "Rostro visible y buena iluminación",
                          "Una sola persona visible y sin ayuda externa"],
            stages=["Teoría", "Práctica de la habilidad", "Defensa con preguntas"],
            free_evaluations_left=remaining, attempts_used=0,
            policy_version=POLICY_VERSION,
            pending_evaluation_id=pending.id if pending else None,
        )

    @classmethod
    async def consent(cls, db, user, teaching_skill_id, payload, ip_address, user_agent):
        if payload.policy_version != POLICY_VERSION:
            raise SkillMatchException(statuscode=409, message="Las condiciones cambiaron. Volvé a leerlas antes de aceptar.")
        offer, skill, pending, _ = await cls.context(db, user, teaching_skill_id, lock=True)
        if pending is not None:
            # Replays retain the original consent timestamp, policy and audit data.
            return pending
        evaluation = Evaluation(
            user_id=user.id, skill_id=skill.id, teaching_skill_id=offer.id,
            status="PENDING_CALIBRATION", biometric_consent_at=datetime.now(timezone.utc),
            policy_version=POLICY_VERSION, ip_address=ip_address[:64],
            user_agent=user_agent[:512], started_at=None,
        )
        db.add(evaluation)
        await db.commit()
        await db.refresh(evaluation)
        return evaluation
