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
from app.schemas.catalog import (
    CANONICAL_LEVELS,
    METRIC_BALL_TOUCH_STREAK,
    WEIGHTS_TOTAL_TOLERANCE,
    RubricSchema,
)


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


def format_percentage(value: float) -> str:
    """90.0 -> "90", 66.666 -> "66.67" (used in Spanish validation messages)."""
    return f"{round(value, 2):.2f}".rstrip("0").rstrip(".")


def weights_total_message(level_name: str, total: float) -> str:
    return (
        f"Los porcentajes de los criterios del nivel «{level_name}» deben sumar 100% "
        f"(actual: {format_percentage(total)}%)."
    )


def ball_target_message(criterion_name: str, level_name: str) -> str:
    return (
        f"El criterio «{criterion_name}» del nivel «{level_name}» requiere un objetivo "
        f"(target) mayor a 0 para el tipo BALL_TOUCH_STREAK."
    )


def weights_total_is_valid(total: float) -> bool:
    return abs(total - 100.0) <= WEIGHTS_TOTAL_TOLERANCE


def _validate_level_criteria(levels) -> None:
    """S1 write rules: per-level unique keys, BALL_TOUCH_STREAK target and 100% weights."""
    for level in levels or []:
        rubric = level.rubric
        if rubric is None or not rubric.criteria:
            continue
        keys = [criterion.key for criterion in rubric.criteria]
        if len(set(keys)) != len(keys):
            raise SkillMatchException(
                statuscode=400,
                message=f"Las claves de los criterios del nivel «{level.name}» no pueden repetirse.",
            )
        for criterion in rubric.criteria:
            if criterion.metric_type == METRIC_BALL_TOUCH_STREAK and criterion.target is None:
                raise SkillMatchException(statuscode=400, message=ball_target_message(criterion.name, level.name))
        total = rubric.weights_total
        if not weights_total_is_valid(total):
            raise SkillMatchException(statuscode=400, message=weights_total_message(level.name, total))


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
        items = list(result.scalars().unique().all())
        if not public_only:
            repaired = False
            for item in items:
                if not item.levels:
                    item.levels = [_make_level({"level_number": number, "name": name})
                                   for number, name in CANONICAL_LEVELS.items()]
                    repaired = True
            if repaired:
                await _commit_catalog(db)
        return items

    @staticmethod
    async def get_skill(db, skill_id, public_only=False):
        stmt = select(Skill).options(selectinload(Skill.levels).selectinload(SkillLevel.rubric)).where(Skill.id == skill_id)
        if public_only:
            stmt = stmt.where(Skill.is_active.is_(True), Skill.category_id.in_(_category_ids(public_only=True)))
        item = (await db.execute(stmt)).scalar_one_or_none()
        if item is None:
            raise _not_found("Habilidad no encontrada")
        if not public_only and not item.levels:
            item.levels = [_make_level({"level_number": number, "name": name})
                           for number, name in CANONICAL_LEVELS.items()]
            await _commit_catalog(db)
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
        _validate_level_criteria(request.levels)
        levels = request.levels
        if not levels:
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
        _reuse_stored_criterion_keys(item, request.levels)
        # Validate before mutating the loaded entity so a rejection leaves nothing dirty.
        _validate_level_criteria(request.levels)
        values = request.model_dump(exclude_unset=True, exclude={"levels"})
        if "name" in values:
            item.slug = await _unique_slug(db, Skill, values["name"], item.id)
        for key, value in values.items():
            setattr(item, key, value)
        if request.levels is not None:
            _sync_levels(item, request.levels)
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


def _reuse_stored_criterion_keys(item, levels) -> None:
    """Criteria sent without key keep the stored key of the same-named criterion of that level."""
    stored_levels = {level.level_number: level for level in item.levels}
    for level in levels or []:
        current = stored_levels.get(level.level_number)
        if level.rubric is None or current is None or current.rubric is None:
            continue
        try:
            stored = RubricSchema.model_validate({"criteria": current.rubric.criteria or []}).criteria
        except ValueError:
            continue  # Malformed legacy JSON: keep the generated keys.
        level.rubric.reuse_keys_by_name(stored)


def _sync_levels(item, levels) -> None:
    """
    Update levels in place matched by `level_number`, so level ids (and the lab datasets
    linked to them through `dataset_samples.skill_level_id`) survive catalog edits.
    New numbers are created and numbers missing from the request are removed.
    """
    existing = {level.level_number: level for level in item.levels}
    kept = set()
    for value in levels:
        data = value.model_dump() if hasattr(value, "model_dump") else dict(value)
        current = existing.get(data["level_number"])
        if current is None or data["level_number"] in kept:
            # Duplicate numbers fall through to an insert and hit the unique constraint (409).
            item.levels.append(_make_level(data))
            continue
        kept.add(current.level_number)
        rubric_data = data.pop("rubric", None) or {}
        current.name = data["name"]
        current.description = data.get("description")
        criteria = [dict(criterion) for criterion in rubric_data.get("criteria", [])]
        if current.rubric is None:
            current.rubric = Rubric(
                instructions=rubric_data.get("instructions"),
                min_score=rubric_data.get("min_score", 70.0),
                criteria=criteria,
            )
        else:
            current.rubric.instructions = rubric_data.get("instructions")
            current.rubric.min_score = rubric_data.get("min_score", 70.0)
            current.rubric.criteria = criteria
    for number, level in existing.items():
        if number not in kept:
            item.levels.remove(level)


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
