from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import aggregate_order_by, insert 
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import SkillMatchException
from app.models.catalog import Category,Skill
from app.models.match import Match
from app.models.teaching_skill import TeachingSkill
from app.models.user import User, UserRole
from app.models.user_learning_skill import UserLearningSkill
from app.schemas.match import MatchResponse

def directional_skills(member_id: UUID, *, member_teaches: bool):
    # Abrevia los dos modelos que aportan ofertas e intereses.
    teaching = TeachingSkill
    learning = UserLearningSkill

    # Si tú enseñas, el candidato es quien aprende. Si tú aprendes, se invierte.
    owner_id = teaching.user_id if member_teaches else learning.user_id
    other_id = learning.user_id if member_teaches else teaching.user_id

    return (
        select(
            other_id.label("counterpart_id"),
            # Agrupa las habilidades de ese candidato en una lista ordenada.
            func.array_agg(aggregate_order_by(Skill.name, Skill.name)).label("skills"),
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
        )
        .group_by(other_id)
    )


def reciprocal_skills(member_id: UUID):
    # Primer sentido. Lo que tú ofreces y la otra persona busca.
    outgoing = directional_skills(member_id, member_teaches=True).subquery()

    # Segundo sentido. Lo que la otra persona ofrece y tú buscas.
    incoming = directional_skills(member_id, member_teaches=False).subquery()

    return (
        select(
            outgoing.c.counterpart_id,
            outgoing.c.skills.label("you_teach"),
            incoming.c.skills.label("they_teach"),
        )
        .select_from(outgoing)
        # INNER JOIN conserva solo candidatos que aparecen en los dos sentidos.
        .join(incoming, incoming.c.counterpart_id == outgoing.c.counterpart_id)
    )


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

    return (
        select(
            Match.id,
            User.full_name.label("counterpart_name"),
            Match.status,
            crossed.c.you_teach,
            crossed.c.they_teach,
        )
        .select_from(crossed)
        .join(User, User.id == crossed.c.counterpart_id)
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