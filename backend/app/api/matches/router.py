from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.exceptions import SkillMatchException
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.match import MatchCompatibilityResponse, MatchResponse
from app.schemas.response import APIResponse
from app.services import match_service
from app.services import match_proposal_service as negotiation
from app.schemas.match_proposal import (
    MessageResponse, MessageWrite, ProposalDecision, ProposalResponse, ProposalWrite,
)

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


@router.get(
    "/{match_id}/compatibility",
    response_model=APIResponse[MatchCompatibilityResponse],
    response_model_exclude={"count"},
    summary="Cálculo y explicabilidad del score de compatibilidad (HU-22)",
    description="Calcula el score de compatibilidad porcentual ponderado y las razones explicativas del match.",
)
async def get_match_compatibility(
    match_id: UUID,
    user: User = Depends(current_member),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[MatchCompatibilityResponse]:
    # Verifica pertenencia estricta del miembro (404 si es ajeno)
    item = await match_service.get_match_compatibility(db, user.id, match_id)
    return APIResponse.ok(
        data=item,
        message=f"Score de compatibilidad calculado: {item.compatibility_score}%.",
    )


@router.get(
    "/user/{user_id}/compatibility",
    response_model=APIResponse[MatchCompatibilityResponse],
    response_model_exclude={"count"},
    summary="Compatibilidad directa con un miembro específico",
)
async def get_counterpart_compatibility(
    user_id: UUID,
    user: User = Depends(current_member),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[MatchCompatibilityResponse]:
    item = await match_service.get_user_compatibility(db, user.id, user_id)
    return APIResponse.ok(
        data=item,
        message=f"Score de compatibilidad con {item.counterpart_name}: {item.compatibility_score}%.",
    )


@router.get("/{match_id}/proposal", response_model=APIResponse[ProposalResponse])
async def read_proposal(
    match_id: UUID,
    user: User = Depends(current_member),
    db: AsyncSession = Depends(get_db),
):
    item = await negotiation.read(db, match_id, user.id)
    return APIResponse(statuscode=200, message="Propuesta consultada.", data=item)



@router.post("/{match_id}/proposals", response_model=APIResponse[ProposalResponse], status_code=201)
async def create_proposal(
    match_id: UUID,
    payload: ProposalWrite,
    user: User = Depends(current_member),
    db: AsyncSession = Depends(get_db),
):
    item = await negotiation.propose(db, match_id, user.id, payload)
    return APIResponse(statuscode=201, message="Propuesta enviada.", data=item)



@router.post("/{match_id}/accept", response_model=APIResponse[ProposalResponse])
async def accept_proposal(
    match_id: UUID,
    payload: ProposalDecision,
    user: User = Depends(current_member),
    db: AsyncSession = Depends(get_db),
):
    item = await negotiation.decide(db, match_id, user.id, payload.proposal_id, accept=True)
    return APIResponse(statuscode=200, message="Intercambio confirmado.", data=item)



@router.post("/{match_id}/decline", response_model=APIResponse[ProposalResponse])
async def decline_proposal(
    match_id: UUID,
    payload: ProposalDecision,
    user: User = Depends(current_member),
    db: AsyncSession = Depends(get_db),
):
    item = await negotiation.decide(db, match_id, user.id, payload.proposal_id, accept=False)
    return APIResponse(statuscode=200, message="Propuesta rechazada.", data=item)



@router.delete("/{match_id}", response_model=APIResponse[None])
async def dismiss_suggestion(
    match_id: UUID,
    user: User = Depends(current_member),
    db: AsyncSession = Depends(get_db),
):
    await negotiation.dismiss(db, match_id, user.id)
    return APIResponse(statuscode=200, message="Sugerencia descartada.")



@router.get("/{match_id}/messages", response_model=APIResponse[list[MessageResponse]])
async def list_messages(
    match_id: UUID,
    page: int = Query(default=1, ge=1),
    user: User = Depends(current_member),
    db: AsyncSession = Depends(get_db),
):
    item, count = await negotiation.list_messages(db, match_id, user.id, page)
    return APIResponse(statuscode=200, message="Mensajes recuperados.", data=item, count=count)



@router.post("/{match_id}/messages", response_model=APIResponse[MessageResponse], status_code=201)
async def send_message(
    match_id: UUID,
    payload: MessageWrite,
    user: User = Depends(current_member),
    db: AsyncSession = Depends(get_db),
):
    item = await negotiation.send_message(db, match_id, user.id, payload.body)
    return APIResponse(statuscode=201, message="Mensaje enviado.", data=item)
