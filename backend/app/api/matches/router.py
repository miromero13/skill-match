from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.exceptions import SkillMatchException
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.match import MatchResponse
from app.schemas.response import APIResponse
from app.services import match_service

# main.py añade el prefijo /api.
router = APIRouter(prefix="/matches", tags=["Matches · HU-21"])


async def current_member(user: User = Depends(get_current_user)) -> User:
    # Reutiliza la autenticación JWT y exige el rol de la pantalla de miembros.
    if user.role != UserRole.MEMBER:
        raise SkillMatchException("Recurso no encontrado", statuscode=404)
    return user


# Se declara primero para que suggestions no se interprete como un UUID.
@router.get("/suggestions", response_model=APIResponse[list[MatchResponse]])
async def list_my_suggestions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(current_member),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[list[MatchResponse]]:
    # El propietario sale de la sesión autenticada.
    items, total = await match_service.list_suggestions(db, user.id, page, page_size)

    # count representa todas las coincidencias recíprocas, no solo esta página.
    return APIResponse.ok(
        data=items,
        count=total,
        message=(
            "Coincidencias recuperadas correctamente."
            if total
            else "Todavía no tienes coincidencias recíprocas."
        ),
    )


@router.get(
    "/{match_id}",
    response_model=APIResponse[MatchResponse],
    response_model_exclude={"count"},
)
async def get_my_suggestion(
    match_id: UUID,
    user: User = Depends(current_member),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[MatchResponse]:
    # El servicio verifica que el solicitante pertenezca a esa coincidencia.
    item = await match_service.get_suggestion(db, user.id, match_id)
    return APIResponse.ok(data=item, message="Coincidencia recuperada correctamente.")