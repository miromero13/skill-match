import math
from typing import Optional
from uuid import UUID
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import Category, Skill
from app.models.teaching_skill import TeachingSkill
from app.models.user import ExchangeModality, User
from app.models.user_block import UserBlock
from app.schemas.search import (
    TutorSearchFilterParams,
    TutorSearchResultItem,
    TutorTeachingSkillItem,
)

LEVEL_ORDER = {
    "BEGINNER": 1,
    "INTERMEDIATE": 2,
    "ADVANCED": 3,
    "EXPERT": 4,
}


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcula la distancia geodésica en kilómetros entre dos coordenadas usando la fórmula de Haversine."""
    earth_radius_km = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    rad_lat1 = math.radians(lat1)
    rad_lat2 = math.radians(lat2)

    a = (
        math.sin(d_lat / 2.0) ** 2
        + math.cos(rad_lat1) * math.cos(rad_lat2) * math.sin(d_lon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return round(earth_radius_km * c, 1)


class SearchService:
    """Servicio de búsqueda facetada y matching de instructores (HU-20 / RF-MAT-01, RF-MAT-02, RF-MAT-11)."""

    @classmethod
    async def search_tutors(
        cls,
        db: AsyncSession,
        params: TutorSearchFilterParams,
        reference_lat: Optional[float] = None,
        reference_lon: Optional[float] = None,
        viewer_id: Optional[UUID] = None,
    ) -> tuple[list[TutorSearchResultItem], int]:
        # Coordenadas efectivas: query param prevalece sobre el perfil del usuario autenticado
        eff_lat = params.latitude if params.latitude is not None else reference_lat
        eff_lon = params.longitude if params.longitude is not None else reference_lon

        stmt = (
            select(TeachingSkill, Skill, Category, User)
            .join(User, TeachingSkill.user_id == User.id)
            .join(Skill, TeachingSkill.skill_id == Skill.id)
            .join(Category, Skill.category_id == Category.id)
            .where(
                User.is_active == True,
                Skill.is_active == True,
            )
        )

        # Exclusión automática de usuarios bloqueados mutuamente (RF-MAT-14 / HU-26)
        if viewer_id is not None:
            blocked_by_viewer = select(UserBlock.blocked_id).where(UserBlock.blocker_id == viewer_id)
            blocking_viewer = select(UserBlock.blocker_id).where(UserBlock.blocked_id == viewer_id)
            stmt = stmt.where(~User.id.in_(blocked_by_viewer), ~User.id.in_(blocking_viewer))

        # Filtro por texto libre
        if params.query and params.query.strip():
            raw_q = params.query.strip().lower()
            stmt = stmt.where(
                or_(
                    func.lower(User.full_name).contains(raw_q),
                    func.lower(User.bio).contains(raw_q),
                    func.lower(Skill.name).contains(raw_q),
                    func.lower(Category.name).contains(raw_q),
                )
            )

        # Filtro por habilidad específica
        if params.skill_id is not None:
            stmt = stmt.where(TeachingSkill.skill_id == params.skill_id)

        # Filtro por categoría
        if params.category_id is not None:
            stmt = stmt.where(Category.id == params.category_id)

        # Filtro estricto por verificación IA (status == 'VERIFICADA')
        if params.verified_only:
            stmt = stmt.where(func.upper(TeachingSkill.status) == "VERIFICADA")

        # Filtro por modalidad de enseñanza
        if params.modality is not None:
            if params.modality == ExchangeModality.VIRTUAL:
                stmt = stmt.where(
                    or_(
                        User.exchange_modality == ExchangeModality.VIRTUAL,
                        User.exchange_modality == ExchangeModality.BOTH,
                    )
                )
            elif params.modality == ExchangeModality.PRESENCIAL:
                stmt = stmt.where(
                    or_(
                        User.exchange_modality == ExchangeModality.PRESENCIAL,
                        User.exchange_modality == ExchangeModality.BOTH,
                    )
                )

        result = await db.execute(stmt)
        rows = result.all()

        # Agrupar por instructor
        tutors_dict: dict[UUID, dict] = {}
        min_level_val = LEVEL_ORDER.get(params.min_level.upper(), 0) if params.min_level else 0

        for row in rows:
            # Compatibilidad con Tuplas de SQLAlchemy o mock objects
            teaching_skill = row[0]
            skill = row[1]
            category = row[2]
            user = row[3]

            # Filtros en memoria para consistencia garantizada y pruebas aisladas
            if params.skill_id and teaching_skill.skill_id != params.skill_id:
                continue
            if params.category_id and category.id != params.category_id:
                continue
            if params.verified_only and (teaching_skill.status or "").upper() != "VERIFICADA":
                continue
            if params.modality is not None:
                if params.modality == ExchangeModality.VIRTUAL and user.exchange_modality not in (ExchangeModality.VIRTUAL, ExchangeModality.BOTH):
                    continue
                if params.modality == ExchangeModality.PRESENCIAL and user.exchange_modality not in (ExchangeModality.PRESENCIAL, ExchangeModality.BOTH):
                    continue
            if params.query and params.query.strip():
                raw_q = params.query.strip().lower()
                matches = (
                    raw_q in (user.full_name or "").lower()
                    or raw_q in (user.bio or "").lower()
                    or raw_q in (skill.name or "").lower()
                    or raw_q in (category.name or "").lower()
                )
                if not matches:
                    continue

            declared_level_val = LEVEL_ORDER.get(teaching_skill.declared_level.upper(), 0)
            if min_level_val > 0 and declared_level_val < min_level_val:
                continue

            is_verified = (teaching_skill.status or "").upper() == "VERIFICADA"

            skill_item = TutorTeachingSkillItem(
                id=teaching_skill.id,
                skill_id=skill.id,
                skill_name=skill.name,
                category_id=category.id,
                category_name=category.name,
                declared_level=teaching_skill.declared_level,
                years_of_experience=teaching_skill.years_of_experience,
                description=teaching_skill.description,
                accepts_points=teaching_skill.accepts_points,
                hourly_points_rate=teaching_skill.hourly_points_rate,
                status=teaching_skill.status,
                is_verified=is_verified,
            )

            if user.id not in tutors_dict:
                # Distancia geodésica si ambas coordenadas existen
                dist_km: Optional[float] = None
                if (
                    eff_lat is not None
                    and eff_lon is not None
                    and user.latitude is not None
                    and user.longitude is not None
                ):
                    dist_km = haversine_distance(eff_lat, eff_lon, user.latitude, user.longitude)

                tutors_dict[user.id] = {
                    "user": user,
                    "distance_km": dist_km,
                    "skills": [],
                }

            tutors_dict[user.id]["skills"].append(skill_item)

        # Construir lista de resultados y aplicar filtro de distancia máxima
        tutor_results: list[TutorSearchResultItem] = []
        for uid, data in tutors_dict.items():
            u = data["user"]
            dist = data["distance_km"]

            # Si se exige distancia máxima y se dispone de radio
            if params.max_distance is not None:
                if dist is not None:
                    if dist > params.max_distance:
                        continue
                else:
                    # Si no tiene coordenadas y la modalidad es presencial estricta, se excluye
                    if params.modality == ExchangeModality.PRESENCIAL:
                        continue

            skills_list = data["skills"]
            has_verified = any(s.is_verified for s in skills_list)

            # Rating base: 5.0 para verificados o con experiencia, 4.8 estándar
            max_exp = max((s.years_of_experience for s in skills_list), default=1)
            calculated_rating = min(5.0, 4.5 + (0.1 * min(5, max_exp)))
            if has_verified:
                calculated_rating = 5.0

            item = TutorSearchResultItem(
                id=u.id,
                full_name=u.full_name,
                avatar_url=u.avatar_url,
                bio=u.bio,
                location_label=u.location_label,
                latitude=u.latitude,
                longitude=u.longitude,
                exchange_modality=u.exchange_modality or ExchangeModality.VIRTUAL,
                presencial_radius_km=u.presencial_radius_km or 10,
                distance_km=dist,
                rating=round(calculated_rating, 1),
                total_reviews=max(1, max_exp * 2) if has_verified else max_exp,
                has_verified_skills=has_verified,
                skills=skills_list,
                created_at=u.created_at,
            )
            tutor_results.append(item)

        # Ordenamiento
        sort_by = (params.sort_by or "reputation").lower()
        if sort_by == "distance":
            tutor_results.sort(
                key=lambda x: (
                    x.distance_km if x.distance_km is not None else 999999.0,
                    not x.has_verified_skills,
                    x.full_name,
                )
            )
        elif sort_by == "points_asc":
            def get_min_rate(t: TutorSearchResultItem) -> float:
                rates = [
                    s.hourly_points_rate
                    for s in t.skills
                    if s.accepts_points and s.hourly_points_rate is not None
                ]
                return min(rates) if rates else 999999.0
            tutor_results.sort(key=lambda x: (get_min_rate(x), not x.has_verified_skills))
        elif sort_by == "points_desc":
            def get_max_rate(t: TutorSearchResultItem) -> float:
                rates = [
                    s.hourly_points_rate
                    for s in t.skills
                    if s.accepts_points and s.hourly_points_rate is not None
                ]
                return max(rates) if rates else -1.0
            tutor_results.sort(key=lambda x: (get_max_rate(x), x.has_verified_skills), reverse=True)
        elif sort_by == "experience":
            tutor_results.sort(
                key=lambda x: max((s.years_of_experience for s in x.skills), default=0),
                reverse=True,
            )
        elif sort_by == "recent":
            tutor_results.sort(
                key=lambda x: x.created_at.timestamp() if x.created_at else 0.0,
                reverse=True,
            )
        else:
            # reputation por defecto: verificados primero, luego rating y experiencia
            tutor_results.sort(
                key=lambda x: (
                    not x.has_verified_skills,
                    -x.rating,
                    -max((s.years_of_experience for s in x.skills), default=0),
                    x.full_name,
                )
            )

        total_count = len(tutor_results)
        start_idx = (params.page - 1) * params.page_size
        end_idx = start_idx + params.page_size
        paginated_items = tutor_results[start_idx:end_idx]

        return paginated_items, total_count
