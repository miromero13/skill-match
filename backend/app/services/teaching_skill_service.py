from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import SkillMatchException
from app.models.catalog import Category, Skill
from app.models.teaching_skill import TeachingSkill
from app.schemas.teaching_skill import TeachingSkillResponse, TeachingSkillWrite

def serialize(item : TeachingSkill , skill_name :str) -> TeachingSkillResponse: 
    return TeachingSkillResponse(
        id = item.id,
        skill_id=item.skill_id,
        skill_name= skill_name,
        declared_level= item.declared_level,
        years_of_experence=item.years_of_experence,
        description= item.description,
        accepts_points=  item.accepts_points,
        hourly_points_rate=  item.hourly_points_rate,
        status=  item.status,
    )

class TeachingSkillService : 
    @staticmethod
    async def available_skills(db : AsyncSession) -> list[Skill]:
        result = await db.scalars(
            select(Skill) 
            .join (Category, Category.id == Skill.category_id)
            .where(Skill.is_active.is_(True), Category.is_active.is_(True))
            .order_by(Skill.name, Skill.id)
        )
        return list(result   )

    @staticmethod
    async def list_owned(
        db: AsyncSession, user_id: UUID, page: int, page_size: int,
    ) -> tuple[list[TeachingSkillResponse], int]:
        total = await db.scalar(
            select(func.count())
            .select_from(TeachingSkill)
            .where(TeachingSkill.user_id == user_id)
        )
        rows = await db.execute(
            select(TeachingSkill, Skill.name)
            .join(Skill, Skill.id == TeachingSkill.skill_id)
            .where(TeachingSkill.user_id == user_id)
            .order_by(TeachingSkill.created_at.desc(), TeachingSkill.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return [serialize(item, name) for item, name in rows], total or 0

    @staticmethod
    async def get_owned(
        db: AsyncSession, user_id: UUID, item_id: UUID,
    ) -> TeachingSkill:
        item = await db.scalar(
            select(TeachingSkill).where(
                TeachingSkill.id == item_id,
                TeachingSkill.user_id == user_id,
            )
        )
        if item is None:
            raise SkillMatchException("Recurso no encontrado", statuscode=404)
        return item

    @staticmethod
    async def save(
        db: AsyncSession,
        user_id: UUID,
        payload: TeachingSkillWrite,
        item_id: UUID | None = None,
    ) -> TeachingSkillResponse:
        item = (
            await TeachingSkillService.get_owned(db, user_id, item_id)
            if item_id is not None else None
        )

        if item is not None and item.skill_id != payload.skill_id:
            raise SkillMatchException(
                "Para cambiar la habilidad, elimina la oferta y crea otra."
            )

        skill = await db.scalar(
            select(Skill)
            .join(Category, Category.id == Skill.category_id)
            .where(
                Skill.id == payload.skill_id,
                Skill.is_active.is_(True),
                Category.is_active.is_(True),
            )
        )
        if skill is None:
            raise SkillMatchException(
                "La habilidad no está disponible.", statuscode=404,
            )

        duplicate_query = select(TeachingSkill.id).where(
            TeachingSkill.user_id == user_id,
            TeachingSkill.skill_id == payload.skill_id,
        )
        if item is not None:
            duplicate_query = duplicate_query.where(TeachingSkill.id != item.id)

        if await db.scalar(duplicate_query):
            raise SkillMatchException(
                "Ya registraste esta habilidad.", statuscode=409,
            )

        values = payload.model_dump()
        values["declared_level"] = payload.declared_level.value

        try:
            async with db.begin_nested():
                if item is None:
                    item = TeachingSkill(
                        user_id=user_id, status="DECLARADA", **values,
                    )
                    db.add(item)
                else:
                    for key, value in values.items():
                        setattr(item, key, value)

                await db.flush()
        except IntegrityError as exc:
            # Cubre también dos altas simultáneas de la misma habilidad.
            original = getattr(exc.orig, "__cause__", None)
            constraint = getattr(original, "constraint_name", None)
            if constraint == "uq_teaching_user_skill":
                raise SkillMatchException(
                    "Ya registraste esta habilidad.", statuscode=409,
                ) from exc
            raise

        return serialize(item, skill.name)

    @staticmethod
    async def delete(
        db: AsyncSession, user_id: UUID, item_id: UUID,
    ) -> None:
        item = await TeachingSkillService.get_owned(db, user_id, item_id)
        await db.delete(item)
        await db.flush()
