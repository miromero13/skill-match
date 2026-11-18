"""Question-bank persistence independent of exam starts and attempt accounting."""
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import SkillMatchException
from app.models.catalog import SkillLevel
from app.models.theory_question import TheoryQuestion
from app.schemas.theory_question import QuestionCreate


class TheoryQuestionService:
    @staticmethod
    async def create(db: AsyncSession, payload: QuestionCreate):
        level = await db.scalar(select(SkillLevel.id).where(
            SkillLevel.skill_id == payload.skill_id, SkillLevel.level_number == payload.level_number,
        ))
        if level is None:
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
