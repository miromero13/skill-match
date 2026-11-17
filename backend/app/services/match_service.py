from uuid import UUID
from sqlalchemy import case, func, literal_column, or_, select
from sqlalchemy.orm import aliased
from sqlalchemy.dialects.postgresql import aggregate_order_by, insert 
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import SkillMatchException
from app.models.catalog import Category, Skill
from app.models.match import Match
from app.models.match_proposal import MatchDismissal
from app.models.teaching_skill import TeachingSkill
from app.models.user import User, UserRole
from app.models.user_availability import UserAvailability
from app.models.user_block import UserBlock
from app.models.user_learning_skill import UserLearningSkill
from app.schemas.match import (
    CompatibilityFactors,
    FactorBreakdown,
    MatchCompatibilityResponse,
    MatchResponse,
)
from app.services.search_service import haversine_distance

LEVEL_MAP: dict[str, int] = {
    "BEGINNER": 1,
    "PRINCIPIANTE": 1,
    "INTERMEDIATE": 2,
    "INTERMEDIO": 2,
    "ELEMENTAL": 2,
    "ADVANCED": 3,
    "AVANZADO": 3,
    "EXPERT": 4,
    "EXPERTO": 4,
    "MASTER": 5,
    "MAESTRO": 5,
}


def to_level_int(val: str | int | None) -> int:
    if val is None:
        return 1
    if isinstance(val, int):
        return val
    if isinstance(val, str):
        val_clean = val.strip().upper()
        if val_clean.isdigit():
            return int(val_clean)
        return LEVEL_MAP.get(val_clean, 1)
    return 1


def normalize_modality(val: object) -> str:
    if val is None:
        return "VIRTUAL"
    if hasattr(val, "value"):
        return str(val.value).upper()
    return str(val).split(".")[-1].upper()


DAY_NAMES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


def parse_time_minutes(time_str: str) -> int:
    try:
        parts = time_str.strip().split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except Exception:
        return 0

def directional_skills(member_id: UUID, *, member_teaches: bool):
    # Abrevia los dos modelos que aportan ofertas e intereses.
    teaching = TeachingSkill
    learning = UserLearningSkill

    # Si tú enseñas, el candidato es quien aprende. Si tú aprendes, se invierte.
    owner_id = teaching.user_id if member_teaches else learning.user_id
    other_id = learning.user_id if member_teaches else teaching.user_id

    # Subconsultas para exclusión automática de bloqueos mutuos (RF-MAT-14 / HU-26)
    blocked_by_me = select(UserBlock.blocked_id).where(UserBlock.blocker_id == member_id)
    blocking_me = select(UserBlock.blocker_id).where(UserBlock.blocked_id == member_id)

    return (
        select(
            other_id.label("counterpart_id"),
            # Agrupa las habilidades de ese candidato en una lista ordenada.
            func.array_agg(aggregate_order_by(Skill.name, Skill.name)).label("skills"),
            func.array_agg(Skill.name)
            .filter(func.upper(teaching.status) == "VERIFICADA").label("verified"),
        )
        .select_from(teaching)
        # El cruce usa el mismo ID del catálogo en ambas tablas.
        .join(learning, learning.skill_id == teaching.skill_id)
        .join(Skill, Skill.id == teaching.skill_id)
        .join(Category, Category.id == Skill.category_id)
        .join(User, User.id == other_id)
        .where(
            owner_id == member_id,          # Limita el cruce al miembro actual.
            other_id != member_id,          # Evita una coincidencia consigo mismo.
            User.role == UserRole.MEMBER,   # Solo sugiere miembros.
            User.is_active.is_(True),       # Excluye las cuentas inactivas.
            User.is_locked.is_(False),      # Excluye las cuentas bloqueadas.
            Skill.is_active.is_(True),      # Considera habilidades publicadas.
            Category.is_active.is_(True),   # Considera categorías activas.
            ~other_id.in_(blocked_by_me),   # Excluye usuarios bloqueados por mí.
            ~other_id.in_(blocking_me),     # Excluye usuarios que me han bloqueado.
        )
        .group_by(other_id)
    )


def reciprocal_skills(member_id: UUID):
    # Primer sentido. Lo que tú ofreces y la otra persona busca.
    outgoing = directional_skills(member_id, member_teaches=True).subquery()

    # Segundo sentido. Lo que la otra persona ofrece y tú buscas.
    incoming = directional_skills(member_id, member_teaches=False).subquery()
    unavailable = (
        select(Match.id)
        .outerjoin(MatchDismissal, (MatchDismissal.match_id == Match.id)
                   & (MatchDismissal.member_id == member_id))
        .where(
            Match.member_a_id == func.least(member_id, outgoing.c.counterpart_id),
            Match.member_b_id == func.greatest(member_id, outgoing.c.counterpart_id),
            (Match.status == "declined") | MatchDismissal.member_id.is_not(None),
        )
        .correlate(outgoing)
        .exists()
    )

    empty_skills = literal_column("ARRAY[]::varchar[]")
    direct = (
        select(
            outgoing.c.counterpart_id,
            outgoing.c.skills.label("you_teach"),
            incoming.c.skills.label("they_teach"),
            func.coalesce(outgoing.c.verified, empty_skills).label("you_verified"),
            func.coalesce(incoming.c.verified, empty_skills).label("they_verified"),
        )
        .select_from(outgoing)
        # INNER JOIN conserva solo candidatos que aparecen en los dos sentidos.
        .join(incoming, incoming.c.counterpart_id == outgoing.c.counterpart_id)
        .where(~unavailable)
    ).cte()
    counterpart = case((Match.member_a_id == member_id, Match.member_b_id), else_=Match.member_a_id)
    # A confirmed exchange remains reachable if a member edits their skills.
    confirmed = select(counterpart, empty_skills, empty_skills, empty_skills, empty_skills).where(
        or_(Match.member_a_id == member_id, Match.member_b_id == member_id),
        Match.status == "confirmed",
        ~select(direct.c.counterpart_id).where(direct.c.counterpart_id == counterpart).exists(),
    )
    return select(direct).union_all(confirmed)


async def save_suggestions(
    db: AsyncSession, member_id: UUID, counterpart_ids: list[UUID],
) -> None:
    # Cada lista paginada genera solo los registros de su página.
    if not counterpart_ids:
        return

    # Ordena cada pareja para que A–B y B–A tengan la misma clave.
    pairs = sorted({tuple(sorted((member_id, other))) for other in counterpart_ids})
    entries = [
        {"member_a_id": first, "member_b_id": second, "status": "pending"}
        for first, second in pairs
    ]

    # Usa la restricción de PostgreSQL para resolver solicitudes simultáneas.
    statement = insert(Match).values(entries).on_conflict_do_nothing(
        constraint="uq_matches_members",
    )
    await db.execute(statement)


def match_details_query(member_id: UUID):
    # Vuelve a comprobar la reciprocidad para no mostrar sugerencias obsoletas.
    crossed = reciprocal_skills(member_id).subquery()
    member = aliased(User)

    return (
        select(
            Match.id,
            User.full_name.label("counterpart_name"),
            User.avatar_url.label("counterpart_avatar_url"),
            member.full_name.label("member_name"),
            member.avatar_url.label("member_avatar_url"),
            Match.status,
            crossed.c.you_teach,
            crossed.c.they_teach,
            crossed.c.you_verified,
            crossed.c.they_verified,
        )
        .select_from(crossed)
        .join(User, User.id == crossed.c.counterpart_id)
        .join(member, member.id == member_id)
        .join(
            Match,
            # least y greatest reproducen el orden guardado por save_suggestions.
            (Match.member_a_id == func.least(member_id, crossed.c.counterpart_id))
            & (Match.member_b_id == func.greatest(member_id, crossed.c.counterpart_id)),
        )
    )


async def list_suggestions(
    db: AsyncSession, member_id: UUID, page: int, page_size: int,
) -> tuple[list[MatchResponse], int]:
    crossed = reciprocal_skills(member_id).subquery()

    # Cuenta personas que cumplen ambos sentidos antes de paginar.
    total = await db.scalar(select(func.count()).select_from(crossed))

    # Ordena por nombre y usa el ID para desempatar.
    counterpart_ids = list(await db.scalars(
        select(crossed.c.counterpart_id)
        .join(User, User.id == crossed.c.counterpart_id)
        .order_by(User.full_name, User.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ))

    # Guarda la sugerencia la primera vez que se devuelve esa página.
    await save_suggestions(db, member_id, counterpart_ids)

    # Carga las filas guardadas y los cruces de habilidades en una consulta.
    rows = await db.execute(
        match_details_query(member_id)
        .where(User.id.in_(counterpart_ids))
        .order_by(User.full_name, User.id)
    )

    return [MatchResponse.model_validate(row) for row in rows.mappings()], total or 0


async def get_suggestion(
    db: AsyncSession, member_id: UUID, match_id: UUID,
) -> MatchResponse:
    # La consulta parte de los cruces del miembro actual y filtra por ID.
    row = (
        await db.execute(match_details_query(member_id).where(Match.id == match_id))
    ).mappings().one_or_none()

    # Una coincidencia ajena, inexistente u obsoleta produce la misma respuesta.
    if row is None:
        raise SkillMatchException("Recurso no encontrado", statuscode=404)

    return MatchResponse.model_validate(row)


async def compute_compatibility_between_users(
    db: AsyncSession,
    user_a: User,
    user_b: User,
    match_id: UUID | None = None,
) -> MatchCompatibilityResponse:
    """Calcula de forma determinística la matriz de compatibilidad ponderada (HU-22 / RF-MAT-04, RF-MAT-06).

    Ponderación:
    - Afinidad de habilidades ofrecidas y demandadas: 40%
    - Coincidencia de disponibilidad horaria semanal: 25%
    - Compatibilidad de modalidad y ubicación geográfica: 20%
    - Nivel de verificación IA y reputación previa: 15%
    """
    reasons: list[str] = []

    # Consultar ofertas y demandas de ambos usuarios
    teaching_a = list((await db.scalars(select(TeachingSkill).where(TeachingSkill.user_id == user_a.id))).all())
    learning_a = list((await db.scalars(select(UserLearningSkill).where(UserLearningSkill.user_id == user_a.id))).all())
    teaching_b = list((await db.scalars(select(TeachingSkill).where(TeachingSkill.user_id == user_b.id))).all())
    learning_b = list((await db.scalars(select(UserLearningSkill).where(UserLearningSkill.user_id == user_b.id))).all())

    # Consultar franjas de disponibilidad activas
    avail_a = list(
        (
            await db.scalars(
                select(UserAvailability).where(
                    UserAvailability.user_id == user_a.id,
                    UserAvailability.is_enabled.is_(True),
                )
            )
        ).all()
    )
    avail_b = list(
        (
            await db.scalars(
                select(UserAvailability).where(
                    UserAvailability.user_id == user_b.id,
                    UserAvailability.is_enabled.is_(True),
                )
            )
        ).all()
    )

    # 1. FACTOR: Afinidad de Habilidades (40%)
    map_teach_a = {ts.skill_id: ts for ts in teaching_a}
    map_learn_b = {ls.skill_id: ls for ls in learning_b}
    map_teach_b = {ts.skill_id: ts for ts in teaching_b}
    map_learn_a = {ls.skill_id: ls for ls in learning_a}

    a_to_b = set(map_teach_a.keys()).intersection(set(map_learn_b.keys()))
    b_to_a = set(map_teach_b.keys()).intersection(set(map_learn_a.keys()))

    if a_to_b and b_to_a:
        skill_score = 75
        for s_id in a_to_b:
            ts = map_teach_a[s_id]
            ls = map_learn_b[s_id]
            teach_lvl = to_level_int(ts.declared_level)
            target_lvl = to_level_int(ls.target_level)
            current_lvl = to_level_int(ls.current_level)
            if teach_lvl >= target_lvl:
                skill_score += 10
            elif teach_lvl >= current_lvl:
                skill_score += 5
        for s_id in b_to_a:
            ts = map_teach_b[s_id]
            ls = map_learn_a[s_id]
            teach_lvl = to_level_int(ts.declared_level)
            target_lvl = to_level_int(ls.target_level)
            current_lvl = to_level_int(ls.current_level)
            if teach_lvl >= target_lvl:
                skill_score += 10
            elif teach_lvl >= current_lvl:
                skill_score += 5
        if len(a_to_b) + len(b_to_a) >= 3:
            skill_score += 10
        skill_score = min(100, skill_score)
        skill_desc = "Reciprocidad simétrica exacta en habilidades"
        reasons.append(
            f"Intercambio recíproco directo ({len(a_to_b)} habilidad(es) ofrecida(s) y {len(b_to_a)} aprendida(s))"
        )
    elif a_to_b or b_to_a:
        skill_score = 50
        skill_desc = "Afinidad unilateral en habilidades formativas"
        reasons.append("Coincidencia unilateral de habilidades para intercambio formativo o compensación de puntos")
    else:
        skill_score = 25
        skill_desc = "Exploración de habilidades complementarias abiertas"

    # 2. FACTOR: Coincidencia de Disponibilidad Horaria (25%)
    overlapping_slots: list[tuple[int, int, int]] = []
    for sa in avail_a:
        for sb in avail_b:
            if sa.day_of_week == sb.day_of_week:
                st_a = parse_time_minutes(sa.start_time)
                en_a = parse_time_minutes(sa.end_time)
                st_b = parse_time_minutes(sb.start_time)
                en_b = parse_time_minutes(sb.end_time)
                ov_start = max(st_a, st_b)
                ov_end = min(en_a, en_b)
                if ov_end - ov_start >= 30:
                    overlapping_slots.append((sa.day_of_week, ov_start, ov_end))

    if overlapping_slots:
        matched_days = sorted(list({DAY_NAMES[s[0]] for s in overlapping_slots}))
        has_weekend = any(s[0] in (5, 6) for s in overlapping_slots)

        if len(overlapping_slots) >= 3:
            schedule_score = 100
        elif len(overlapping_slots) == 2:
            schedule_score = 90
        else:
            schedule_score = 75

        schedule_desc = f"Horarios coincidentes en {', '.join(matched_days)}"
        if has_weekend:
            reasons.append("Ambos disponibles fines de semana")
        reasons.append(
            f"Disponibilidad horaria coincidente ({len(overlapping_slots)} bloques de tiempo compatibles)"
        )
    else:
        if len(avail_a) == 0 or len(avail_b) == 0:
            schedule_score = 65
            schedule_desc = "Horarios abiertos por coordinar directamente"
            reasons.append("Disponibilidad horaria flexible a convenir entre miembros")
        else:
            schedule_score = 30
            schedule_desc = "Sin coincidencia en agendas habituales"
            reasons.append("Requiere acordar una sesión fuera de los horarios registrados")

    # 3. FACTOR: Modalidad y Ubicación (20%)
    mod_a = normalize_modality(user_a.exchange_modality)
    mod_b = normalize_modality(user_b.exchange_modality)

    if mod_a == "VIRTUAL" and mod_b == "VIRTUAL":
        modality_score = 100
        modality_desc = "Modalidad virtual compartida"
        reasons.append("Modalidad virtual 100% compatible")
    elif mod_a == "BOTH" or mod_b == "BOTH":
        modality_score = 95
        modality_desc = "Modalidad híbrida flexible (online o presencial)"
        reasons.append("Flexibilidad total: uno o ambos miembros aceptan modalidad híbrida")
    elif mod_a == "PRESENCIAL" and mod_b == "PRESENCIAL":
        if (
            user_a.latitude is not None
            and user_a.longitude is not None
            and user_b.latitude is not None
            and user_b.longitude is not None
        ):
            dist = haversine_distance(user_a.latitude, user_a.longitude, user_b.latitude, user_b.longitude)
            rad_eff = min(user_a.presencial_radius_km or 10, user_b.presencial_radius_km or 10)
            if dist <= rad_eff:
                modality_score = 100
                modality_desc = f"Encuentros presenciales cercanos ({dist} km)"
                reasons.append(f"Ubicación cercana dentro del radio óptimo de cobertura ({dist} km)")
            elif dist <= max(user_a.presencial_radius_km or 10, user_b.presencial_radius_km or 10):
                modality_score = 80
                modality_desc = f"Encuentros presenciales en radio ampliado ({dist} km)"
                reasons.append(f"Cercanía geográfica aceptable ({dist} km)")
            else:
                modality_score = max(25, int(100 - dist))
                modality_desc = f"Distancia física de {dist} km"
        else:
            modality_score = 75
            modality_desc = "Modalidad presencial compartida en la misma región"
            reasons.append("Ambos miembros prefieren encuentros presenciales")
    else:
        modality_score = 25
        modality_desc = "Preferencia dispar de modalidad (virtual vs presencial)"

    # 4. FACTOR: Verificación IA y Reputación (15%)
    all_teach = teaching_a + teaching_b
    has_verified = any((ts.status or "").upper() == "VERIFICADA" for ts in all_teach)

    reputation_score = 20
    if has_verified:
        reputation_score += 45
        reasons.append("Habilidad evaluada y verificada por IA de SkillMatch")

    if user_a.biometric_enrolled_at is not None or user_b.biometric_enrolled_at is not None:
        reputation_score += 20
        reasons.append("Miembro con identidad y perfil biométrico autenticado")

    max_exp = max([ts.years_of_experience for ts in all_teach], default=0)
    if max_exp >= 3:
        reputation_score += 15
        reasons.append(f"Instructor con sólida trayectoria ({max_exp} años de experiencia)")

    reputation_score = min(100, reputation_score)
    reputation_desc = (
        "Sello de verificación IA activo" if has_verified else "Perfil comunitario validado"
    )

    # Cálculo Ponderado Global
    w_skill = round(skill_score * 0.40, 1)
    w_sched = round(schedule_score * 0.25, 1)
    w_modal = round(modality_score * 0.20, 1)
    w_reput = round(reputation_score * 0.15, 1)

    total_compatibility = min(100, max(0, round(w_skill + w_sched + w_modal + w_reput)))

    factors = CompatibilityFactors(
        skill_affinity=FactorBreakdown(
            score=skill_score,
            weight=40,
            weighted_score=w_skill,
            description=skill_desc,
        ),
        schedule_overlap=FactorBreakdown(
            score=schedule_score,
            weight=25,
            weighted_score=w_sched,
            description=schedule_desc,
        ),
        modality_location=FactorBreakdown(
            score=modality_score,
            weight=20,
            weighted_score=w_modal,
            description=modality_desc,
        ),
        reputation_verification=FactorBreakdown(
            score=reputation_score,
            weight=15,
            weighted_score=w_reput,
            description=reputation_desc,
        ),
    )

    return MatchCompatibilityResponse(
        match_id=match_id,
        counterpart_id=user_b.id,
        counterpart_name=user_b.full_name,
        compatibility_score=total_compatibility,
        factors=factors,
        match_reasons=reasons,
    )


async def get_match_compatibility(
    db: AsyncSession, member_id: UUID, match_id: UUID,
) -> MatchCompatibilityResponse:
    """Retorna la compatibilidad detallada de un match, garantizando ofuscación 404 si el usuario es ajeno."""
    # Consultar el match
    match = await db.get(Match, match_id)
    if not match:
        raise SkillMatchException("Recurso no encontrado", statuscode=404)

    # Política estricta de ofuscación: 404 Not Found si no es participante del match
    if match.member_a_id != member_id and match.member_b_id != member_id:
        raise SkillMatchException("Recurso no encontrado", statuscode=404)

    counterpart_id = match.member_b_id if match.member_a_id == member_id else match.member_a_id
    user_a = await db.get(User, member_id)
    user_b = await db.get(User, counterpart_id)

    if not user_a or not user_b:
        raise SkillMatchException("Recurso no encontrado", statuscode=404)

    return await compute_compatibility_between_users(
        db, user_a, user_b, match_id=match.id
    )


async def get_user_compatibility(
    db: AsyncSession, member_id: UUID, counterpart_id: UUID,
) -> MatchCompatibilityResponse:
    """Calcula la compatibilidad entre dos miembros directamente (para vistas previas y diálogo de propuestas)."""
    if member_id == counterpart_id:
        raise SkillMatchException("No es posible calcular compatibilidad consigo mismo", statuscode=400)

    user_a = await db.get(User, member_id)
    user_b = await db.get(User, counterpart_id)

    if not user_a or not user_b or not user_b.is_active or user_b.is_locked:
        raise SkillMatchException("Recurso no encontrado", statuscode=404)

    existing_match = await db.scalar(
        select(Match).where(
            (Match.member_a_id == func.least(member_id, counterpart_id))
            & (Match.member_b_id == func.greatest(member_id, counterpart_id))
        )
    )

    return await compute_compatibility_between_users(
        db, user_a, user_b, match_id=existing_match.id if existing_match else None
    )
