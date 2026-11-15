import re
import unicodedata
import uuid
from typing import Optional

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import SkillMatchException
from app.models.catalog import Category, ChallengeType, Rubric, Skill, SkillLevel
from app.schemas.catalog import CANONICAL_LEVELS


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.strip().lower())
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", ascii_value)).strip("-")


async def _unique_slug(db: AsyncSession, model, value: str, exclude_id=None) -> str:
    base = _slug(value) or "item"
    candidate, suffix = base, 2
    while True:
        stmt = select(model.id).where(model.slug == candidate)
        if exclude_id is not None:
            stmt = stmt.where(model.id != exclude_id)
        if (await db.execute(stmt)).scalar_one_or_none() is None:
            return candidate
        candidate = f"{base}-{suffix}"
        suffix += 1


async def _persist(db, item):
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


class CatalogService:
    @staticmethod
    async def list_categories(db):
        result = await db.execute(select(Category).order_by(Category.name))
        return list(result.scalars().all())

    @staticmethod
    async def create_category(db, request):
        item = Category(name=request.name.strip(), slug=await _unique_slug(db, Category, request.name), description=request.description, is_active=request.is_active)
        return await _persist(db, item)

    @staticmethod
    async def update_category(db, category_id, request):
        item = await db.get(Category, category_id)
        if item is None:
            raise _not_found("Categoría no encontrada")
        values = request.model_dump(exclude_unset=True)
        if "name" in values:
            values["name"] = values["name"].strip()
            item.slug = await _unique_slug(db, Category, values["name"], item.id)
        for key, value in values.items():
            setattr(item, key, value)
        return await _persist(db, item)

    @staticmethod
    async def delete_category(db, category_id):
        item = await db.get(Category, category_id)
        if item is None:
            raise _not_found("Categoría no encontrada")
        await db.delete(item)
        await db.commit()

    @staticmethod
    async def list_challenge_types(db):
        result = await db.execute(select(ChallengeType).order_by(ChallengeType.name))
        return list(result.scalars().all())

    @staticmethod
    async def create_challenge_type(db, request):
        item = ChallengeType(name=request.name.strip(), code=request.code.strip().upper(), evaluation_modality=request.evaluation_modality.strip().upper(), description=request.description, is_active=request.is_active)
        return await _persist(db, item)

    @staticmethod
    async def list_skills(db, category_id: Optional[uuid.UUID] = None, search: Optional[str] = None):
        stmt = select(Skill).options(selectinload(Skill.levels).selectinload(SkillLevel.rubric)).order_by(Skill.name)
        if category_id:
            stmt = stmt.where(Skill.category_id == category_id)
        if search:
            stmt = stmt.where(func.lower(Skill.name).contains(search.strip().lower()))
        result = await db.execute(stmt)
        return list(result.scalars().unique().all())

    @staticmethod
    async def get_skill(db, skill_id):
        result = await db.execute(select(Skill).options(selectinload(Skill.levels).selectinload(SkillLevel.rubric)).where(Skill.id == skill_id))
        item = result.scalar_one_or_none()
        if item is None:
            raise _not_found("Habilidad no encontrada")
        return item

    @staticmethod
    async def create_skill(db, request):
        levels = request.levels
        if levels is None:
            levels = []
            for number, name in CANONICAL_LEVELS.items():
                levels.append({"level_number": number, "name": name})
        item = Skill(
            category_id=request.category_id, challenge_type_id=request.challenge_type_id,
            name=request.name.strip(), slug=await _unique_slug(db, Skill, request.name),
            description=request.description, min_approval_threshold=request.min_approval_threshold,
            is_ready_to_publish=request.is_ready_to_publish, is_active=False,
        )
        item.levels = [_make_level(level) for level in levels]
        db.add(item)
        await db.commit()
        result = await db.execute(select(Skill).options(selectinload(Skill.levels).selectinload(SkillLevel.rubric)).where(Skill.id == item.id))
        return result.scalar_one()

    @staticmethod
    async def update_skill(db, skill_id, request):
        item = await CatalogService.get_skill(db, skill_id)
        values = request.model_dump(exclude_unset=True, exclude={"levels"})
        if "name" in values:
            values["name"] = values["name"].strip()
            item.slug = await _unique_slug(db, Skill, values["name"], item.id)
        for key, value in values.items():
            setattr(item, key, value)
        if request.levels is not None:
            for lvl in list(item.levels):
                await db.delete(lvl)
            item.levels.clear()
            await db.flush()
            for level in request.levels:
                item.levels.append(_make_level(level))
        await db.commit()
        return await CatalogService.get_skill(db, item.id)

    @staticmethod
    async def toggle_ready(db, skill_id, is_ready):
        item = await CatalogService.get_skill(db, skill_id)
        item.is_ready_to_publish = is_ready
        await db.commit()
        return await CatalogService.get_skill(db, skill_id)

    @staticmethod
    async def toggle_status(db, skill_id, is_active):
        item = await CatalogService.get_skill(db, skill_id)
        item.is_active = is_active
        await db.commit()
        return await CatalogService.get_skill(db, skill_id)

    @staticmethod
    async def delete_skill(db, skill_id):
        item = await db.get(Skill, skill_id)
        if item is None:
            raise _not_found("Habilidad no encontrada")
        await db.delete(item)
        await db.commit()


def _make_level(value):
    data = value.model_dump() if hasattr(value, "model_dump") else value
    rubric_data = data.pop("rubric", None)
    level = SkillLevel(**data)
    rubric_data = rubric_data or {}
    rubric = Rubric(
        instructions=rubric_data.get("instructions"),
        min_score=rubric_data.get("min_score", 70.0),
        criteria=[item.model_dump() if hasattr(item, "model_dump") else item for item in rubric_data.get("criteria", [])],
    )
    level.rubric = rubric
    return level


def _not_found(message):
    return SkillMatchException(statuscode=status.HTTP_404_NOT_FOUND, message=message)
