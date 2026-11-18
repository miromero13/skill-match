import re
import unicodedata
import uuid
from typing import Optional

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.catalog_names import catalog_name_key
from app.core.exceptions import SkillMatchException
from app.models.catalog import Category, ChallengeType, Rubric, Skill, SkillLevel
from app.models.teaching_skill import TeachingSkill
from app.models.user_learning_skill import UserLearningSkill
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


async def _commit_catalog(db):
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise SkillMatchException(statuscode=409, message="El catálogo cambió durante la operación. Revisá los nombres duplicados e intentá nuevamente.")


async def _ensure_unique_name(db, model, name, scope, exclude_id=None):
    stmt = select(model.id).where(model.normalized_name == catalog_name_key(name), scope)
    if exclude_id is not None:
        stmt = stmt.where(model.id != exclude_id)
    if (await db.execute(stmt)).scalar_one_or_none() is not None:
        message = ("Ya existe una habilidad con ese nombre en esta categoría." if model is Skill
                   else "Ya existe una categoría con ese nombre en esta ubicación.")
        raise SkillMatchException(statuscode=409, message=message)


async def _ensure_parent(db, parent_id, category_id=None):
    if parent_id is None:
        return
    if category_id is not None:
        # Serialize hierarchy edits so competing moves cannot introduce a cycle.
        await db.execute(select(Category).order_by(Category.id).with_for_update().execution_options(populate_existing=True))
    visited = {category_id} if category_id else set()
    while parent_id is not None:
        if parent_id in visited:
            raise SkillMatchException(statuscode=400, message="La jerarquía de categorías no puede contener ciclos.")
        visited.add(parent_id)
        parent = await db.get(Category, parent_id)
        if parent is None:
            raise _not_found("Categoría superior no encontrada")
        parent_id = parent.parent_id


def _category_ids(category_id=None, public_only=False):
    stmt = select(Category.id)
    if category_id is not None:
        stmt = stmt.where(Category.id == category_id)
    else:
        stmt = stmt.where(Category.parent_id.is_(None))
    if public_only:
        stmt = stmt.where(Category.is_active.is_(True))
    tree = stmt.cte("visible_categories" if public_only else "category_branch", recursive=True)
    children = select(Category.id).join(tree, Category.parent_id == tree.c.id)
    if public_only:
        children = children.where(Category.is_active.is_(True))
    # UNION terminates even if pre-existing external data contains a cycle.
    return select(tree.union(children).c.id)


class CatalogService:
    @staticmethod
    async def list_categories(db, public_only=False):
        stmt = select(Category).order_by(Category.name)
        if public_only:
            stmt = stmt.where(Category.id.in_(_category_ids(public_only=True)))
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def create_category(db, request):
        await _ensure_parent(db, request.parent_id)
        await _ensure_unique_name(db, Category, request.name, Category.parent_id == request.parent_id)
        item = Category(name=request.name, slug=await _unique_slug(db, Category, request.name),
                        parent_id=request.parent_id, description=request.description, is_active=request.is_active)
        db.add(item)
        await _commit_catalog(db)
        await db.refresh(item)
        return item

    @staticmethod
    async def update_category(db, category_id, request):
        item = await db.get(Category, category_id)
        if item is None:
            raise _not_found("Categoría no encontrada")
        values = request.model_dump(exclude_unset=True)
        parent_id = values.get("parent_id", item.parent_id)
        if "parent_id" in values:
            await _ensure_parent(db, parent_id, item.id)
        await _ensure_unique_name(db, Category, values.get("name", item.name), Category.parent_id == parent_id, item.id)
        if "name" in values:
            item.slug = await _unique_slug(db, Category, values["name"], item.id)
        for key, value in values.items():
            setattr(item, key, value)
        await _commit_catalog(db)
        await db.refresh(item)
        return item

    @staticmethod
    async def delete_category(db, category_id):
        item = await db.get(Category, category_id)
        if item is None:
            raise _not_found("Categoría no encontrada")
        item.is_active = False
        await _commit_catalog(db)

    @staticmethod
    async def list_challenge_types(db):
        result = await db.execute(select(ChallengeType).order_by(ChallengeType.name))
        return list(result.scalars().all())

    @staticmethod
    async def create_challenge_type(db, request):
        item = ChallengeType(name=request.name.strip(), code=request.code.strip().upper(), evaluation_modality=request.evaluation_modality.strip().upper(), description=request.description, is_active=request.is_active)
        return await _persist(db, item)

    @staticmethod
    async def list_skills(db, category_id: Optional[uuid.UUID] = None, search: Optional[str] = None, public_only=False):
        stmt = select(Skill).options(selectinload(Skill.levels).selectinload(SkillLevel.rubric)).order_by(Skill.name)
        if category_id:
            stmt = stmt.where(Skill.category_id.in_(_category_ids(category_id)))
        if public_only:
            stmt = stmt.where(Skill.is_active.is_(True), Skill.category_id.in_(_category_ids(public_only=True)))
        if search:
            stmt = stmt.where(func.lower(Skill.name).contains(search.strip().lower()))
        result = await db.execute(stmt)
        return list(result.scalars().unique().all())

    @staticmethod
    async def get_skill(db, skill_id, public_only=False):
        stmt = select(Skill).options(selectinload(Skill.levels).selectinload(SkillLevel.rubric)).where(Skill.id == skill_id)
        if public_only:
            stmt = stmt.where(Skill.is_active.is_(True), Skill.category_id.in_(_category_ids(public_only=True)))
        item = (await db.execute(stmt)).scalar_one_or_none()
        if item is None:
            raise _not_found("Habilidad no encontrada")
        return item

    @staticmethod
    async def _validate_skill_references(db, category_id, challenge_type_id):
        if await db.get(Category, category_id) is None:
            raise _not_found("Categoría no encontrada")
        if challenge_type_id and await db.get(ChallengeType, challenge_type_id) is None:
            raise _not_found("Tipo de desafío no encontrado")

    @staticmethod
    async def create_skill(db, request):
        await CatalogService._validate_skill_references(db, request.category_id, request.challenge_type_id)
        await _ensure_unique_name(db, Skill, request.name, Skill.category_id == request.category_id)
        levels = request.levels
        if levels is None:
            levels = [{"level_number": number, "name": name} for number, name in CANONICAL_LEVELS.items()]
        item = Skill(
            category_id=request.category_id, challenge_type_id=request.challenge_type_id,
            name=request.name, slug=await _unique_slug(db, Skill, request.name),
            description=request.description, min_approval_threshold=request.min_approval_threshold,
            is_ready_to_publish=request.is_ready_to_publish, is_active=False,
        )
        item.levels = [_make_level(level) for level in levels]
        db.add(item)
        await _commit_catalog(db)
        return await CatalogService.get_skill(db, item.id)

    @staticmethod
    async def update_skill(db, skill_id, request):
        item = await CatalogService.get_skill(db, skill_id)
        await CatalogService._validate_skill_references(db, request.category_id, request.challenge_type_id)
        await _ensure_unique_name(db, Skill, request.name, Skill.category_id == request.category_id, item.id)
        values = request.model_dump(exclude_unset=True, exclude={"levels"})
        if "name" in values:
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
        await _commit_catalog(db)
        return await CatalogService.get_skill(db, item.id)

    @staticmethod
    async def toggle_ready(db, skill_id, is_ready):
        item = await CatalogService.get_skill(db, skill_id)
        item.is_ready_to_publish = is_ready
        await _commit_catalog(db)
        return await CatalogService.get_skill(db, skill_id)

    @staticmethod
    async def toggle_status(db, skill_id, is_active):
        item = await CatalogService.get_skill(db, skill_id)
        item.is_active = is_active
        await _commit_catalog(db)
        return await CatalogService.get_skill(db, skill_id)

    @staticmethod
    async def delete_skill(db, skill_id):
        item = await db.get(Skill, skill_id)
        if item is None:
            raise _not_found("Habilidad no encontrada")
        for model in (UserLearningSkill, TeachingSkill):
            linked = await db.execute(select(model.id).where(model.skill_id == skill_id).limit(1))
            if linked.scalar_one_or_none() is not None:
                raise SkillMatchException(statuscode=409, message="La habilidad tiene miembros vinculados. Desactivala sin eliminar sus asociaciones.")
        item.is_active = False
        await _commit_catalog(db)


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
