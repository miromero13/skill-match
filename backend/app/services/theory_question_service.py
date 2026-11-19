"""Question-bank persistence independent of exam starts and attempt accounting."""
from math import isclose

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import SkillMatchException
from app.models.catalog import Rubric, Skill, SkillLevel
from app.models.theory_question import TheoryQuestion
from app.schemas.catalog import CANONICAL_LEVELS
from app.schemas.theory_question import QuestionCreate


class TheoryQuestionService:
    @staticmethod
    async def create(db: AsyncSession, payload: QuestionCreate):
        level = await db.scalar(select(SkillLevel.id).where(
            SkillLevel.skill_id == payload.skill_id, SkillLevel.level_number == payload.level_number,
        ))
        if level is None:
            skill_exists = await db.scalar(select(Skill.id).where(Skill.id == payload.skill_id))
            has_any_levels = await db.scalar(
                select(SkillLevel.id).where(SkillLevel.skill_id == payload.skill_id).limit(1)
            )
            if skill_exists is not None and has_any_levels is None and payload.level_number in CANONICAL_LEVELS:
                for number, name in CANONICAL_LEVELS.items():
                    sl = SkillLevel(skill_id=payload.skill_id, level_number=number, name=name)
                    sl.rubric = Rubric(min_score=70.0, criteria=[])
                    db.add(sl)
                await db.flush()
            else:
                raise SkillMatchException(statuscode=404, message="Habilidad o nivel no encontrado")
        item = TheoryQuestion(
            skill_id=payload.skill_id, level_number=payload.level_number,
            content=payload.model_dump(mode="json", exclude={"skill_id", "level_number"}),
        )
        db.add(item)
        await db.commit()
        await db.refresh(item)
        return item

    @staticmethod
    async def get(db: AsyncSession, question_id):
        item = await db.scalar(select(TheoryQuestion).where(TheoryQuestion.id == question_id)
                               .order_by(TheoryQuestion.version.desc()).limit(1))
        if item is None:
            raise SkillMatchException(statuscode=404, message="Recurso no encontrado")
        return item

    @staticmethod
    async def page(db: AsyncSession, skill_id, level_number, status, offset, limit):
        latest = select(TheoryQuestion.id, func.max(TheoryQuestion.version).label("version")).group_by(
            TheoryQuestion.id).subquery()
        query = select(TheoryQuestion).join(latest, and_(TheoryQuestion.id == latest.c.id,
                                                       TheoryQuestion.version == latest.c.version))
        if skill_id is not None:
            query = query.where(TheoryQuestion.skill_id == skill_id)
        if level_number is not None:
            query = query.where(TheoryQuestion.level_number == level_number)
        if status is not None:
            query = query.where(TheoryQuestion.status == status)
        count = await db.scalar(select(func.count()).select_from(query.subquery()))
        items = (await db.scalars(query.order_by(TheoryQuestion.created_at.desc(), TheoryQuestion.id)
                                  .offset(offset).limit(limit))).all()
        return items, count


    @staticmethod
    def validate_publication(content):
        criteria = content["criteria"]
        if (not content["reference_answer"].strip() or not criteria
                or not isclose(sum(c["weight"] for c in criteria), 100, abs_tol=0.001)):
            raise SkillMatchException(statuscode=400, message="Completá la respuesta de referencia y una rúbrica con pesos que sumen 100.")
        choices = content["choices"]
        codes = [choice["code"] for choice in choices]
        if content["kind"] == "OPEN":
            if choices or content["correct_choice"] is not None:
                raise SkillMatchException(statuscode=400, message="Las preguntas abiertas no admiten opciones.")
        elif (len(codes) < 2 or len(set(codes)) != len(codes)
              or content["correct_choice"] not in codes):
            raise SkillMatchException(statuscode=400, message="La pregunta debe tener opciones únicas y una respuesta correcta válida.")
        elif content["kind"] == "TRUE_FALSE" and set(codes) != {"TRUE", "FALSE"}:
            raise SkillMatchException(statuscode=400, message="Verdadero/falso requiere las opciones TRUE y FALSE.")

    @classmethod
    async def revise(cls, db, question_id, expected_version, action, content=None):
        # The immutable first revision is a stable row lock for all later edits.
        anchor = await db.scalar(select(TheoryQuestion).where(
            TheoryQuestion.id == question_id, TheoryQuestion.version == 1,
        ).with_for_update())
        if anchor is None:
            raise SkillMatchException(statuscode=404, message="Recurso no encontrado")
        latest = await cls.get(db, question_id)
        if latest.version != expected_version:
            raise SkillMatchException(statuscode=409, message="La pregunta cambió. Recargá la última versión antes de guardar.")
        status = {"edit": "DRAFT", "publish": "PUBLISHED", "archive": "ARCHIVED"}[action]
        next_content = content.model_dump(mode="json") if content is not None else latest.content
        if action == "publish":
            cls.validate_publication(next_content)
        revision = TheoryQuestion(id=latest.id, version=latest.version + 1,
                                  skill_id=latest.skill_id, level_number=latest.level_number,
                                  status=status, content=next_content)
        db.add(revision)
        await db.commit()
        await db.refresh(revision)
        return revision

    @classmethod
    async def history(cls, db, question_id):
        await cls.get(db, question_id)
        return (await db.scalars(select(TheoryQuestion).where(TheoryQuestion.id == question_id)
                                .order_by(TheoryQuestion.version))).all()
