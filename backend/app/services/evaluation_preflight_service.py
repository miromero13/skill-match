"""Shared preparation for all disciplines, without an exam-start bypass."""
from datetime import datetime, timezone
from math import ceil

from sqlalchemy import and_, distinct, func, select

from app.core.exceptions import SkillMatchException
from app.models.catalog import Category, ChallengeType, Skill
from app.models.evaluation import Evaluation
from app.models.teaching_skill import TeachingSkill
from app.models.theory_question import TheoryQuestion
from app.models.user import User, UserRole
from app.schemas.evaluation import EvaluationPreflightResponse

POLICY_VERSION = "v1.0"
FREE_SKILLS = 3
ENROLLMENT_REQUIRED = "Debe registrar su rostro testigo en su perfil antes de solicitar una certificación"
QUOTA_EXHAUSTED = "Límite de evaluaciones gratuitas alcanzado para esta habilidad"
CODE_CHALLENGE_CODES = {"CODE_AST"}
CODE_MODALITIES = {"sandbox", "code"}
CODE_CATEGORY_KEYS = {"programacion", "programming"}

DECLARED_LEVEL_MAP: dict[str, tuple[int, str]] = {
    "BEGINNER": (1, "Nivel 1 · Principiante"),
    "ELEMENTAL": (2, "Nivel 2 · Elemental"),
    "INTERMEDIATE": (3, "Nivel 3 · Intermedio"),
    "ADVANCED": (4, "Nivel 4 · Avanzado"),
    "EXPERT": (5, "Nivel 5 · Experto / Master Pedagogo"),
}


def resolve_declared_level(declared_level: str | None) -> tuple[int, str]:
    key = (declared_level or "BEGINNER").strip().upper()
    return DECLARED_LEVEL_MAP.get(key, (1, "Nivel 1 · Principiante"))


def _stages_for_skill(category: Category, challenge_type: ChallengeType | None) -> list[str]:
    if challenge_type is not None:
        has_defense = (
            (challenge_type.code or "").strip().upper() in CODE_CHALLENGE_CODES
            or (challenge_type.evaluation_modality or "").strip().lower() in CODE_MODALITIES
        )
    else:
        has_defense = (
            (category.normalized_name or "").strip().lower() in CODE_CATEGORY_KEYS
            or "program" in (category.slug or "").strip().lower()
        )
    stages = ["Teoría", "Práctica de la habilidad"]
    if has_defense:
        stages.append("Defensa con preguntas")
    return stages


async def _estimated_duration_minutes(db, skill_id, level_number: int, stages: list[str]) -> int:
    latest = (
        select(TheoryQuestion.id, func.max(TheoryQuestion.version).label("version"))
        .group_by(TheoryQuestion.id)
        .subquery()
    )
    published = (
        await db.scalars(
            select(TheoryQuestion)
            .join(latest, and_(TheoryQuestion.id == latest.c.id, TheoryQuestion.version == latest.c.version))
            .where(
                TheoryQuestion.skill_id == skill_id,
                TheoryQuestion.level_number == level_number,
                TheoryQuestion.status == "PUBLISHED",
            )
        )
    ).all()
    if len(published) >= 5:
        sample = sorted((int(q.content.get("time_limit_seconds", 90)) for q in published), reverse=True)[:5]
        theory_minutes = max(5, min(10, ceil(sum(sample) / 60)))
    else:
        theory_minutes = 10
    practice_minutes = 15 if len(stages) == 3 else 10
    return theory_minutes + practice_minutes


class EvaluationPreflightService:
    @staticmethod
    async def context(db, user, teaching_skill_id, *, lock=False):
        # Serialize consent creation per member, without debiting or reserving a start.
        if lock:
            user = await db.scalar(select(User).where(User.id == user.id).with_for_update())
        result = await db.execute(
            select(TeachingSkill, Skill, Category, ChallengeType)
            .join(Skill, TeachingSkill.skill_id == Skill.id)
            .join(Category, Skill.category_id == Category.id)
            .outerjoin(ChallengeType, Skill.challenge_type_id == ChallengeType.id)
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
        offer, skill, category, challenge_type = row
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
        return offer, skill, category, challenge_type, pending, FREE_SKILLS - used_skills

    @classmethod
    async def preflight(cls, db, user, teaching_skill_id):
        offer, skill, category, challenge_type, pending, remaining = await cls.context(db, user, teaching_skill_id)
        target_level_number, declared_level_label = resolve_declared_level(offer.declared_level)
        stages = _stages_for_skill(category, challenge_type)
        duration = await _estimated_duration_minutes(db, skill.id, target_level_number, stages)
        return EvaluationPreflightResponse(
            teaching_skill_id=offer.id, skill_name=skill.name,
            declared_level=offer.declared_level,
            declared_level_label=declared_level_label,
            target_level_number=target_level_number,
            syllabus=skill.description or skill.name,
            requirements=["Cámara y micrófono disponibles", "Rostro visible y buena iluminación",
                          "Una sola persona visible y sin ayuda externa"],
            stages=stages,
            estimated_duration_minutes=duration,
            free_evaluations_left=remaining, attempts_used=0,
            policy_version=POLICY_VERSION,
            pending_evaluation_id=pending.id if pending else None,
        )

    @classmethod
    async def consent(cls, db, user, teaching_skill_id, payload, ip_address, user_agent):
        if payload.policy_version != POLICY_VERSION:
            raise SkillMatchException(statuscode=409, message="Las condiciones cambiaron. Volvé a leerlas antes de aceptar.")
        offer, skill, _, _, pending, _ = await cls.context(db, user, teaching_skill_id, lock=True)
        if pending is not None:
            # Replays retain the original consent timestamp, policy and audit data,
            # but never reuse a prior calibration before the exam has started.
            if pending.started_at is None and pending.status == "READY_FOR_THEORY":
                pending.status = "PENDING_CALIBRATION"
                await db.commit()
                await db.refresh(pending)
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
