from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import SkillMatchException
from app.models.match import Match
from app.models.match_proposal import MatchDismissal, MatchMessage, MatchProposal
from app.schemas.match_proposal import MessageResponse, ProposalResponse, ProposalWrite
from app.services.match_service import get_suggestion


def conflict(message: str) -> SkillMatchException:
    return SkillMatchException(message, statuscode=409)


async def participant_match(db: AsyncSession, match_id: UUID, member_id: UUID, *, lock=False):
    query = select(Match).where(
        Match.id == match_id,
        or_(Match.member_a_id == member_id, Match.member_b_id == member_id),
    )
    match = await db.scalar(query.with_for_update() if lock else query)
    if match is None:
        raise SkillMatchException("Recurso no encontrado", statuscode=404)
    return match


async def latest(db: AsyncSession, match_id: UUID):
    return await db.scalar(
        select(MatchProposal).where(MatchProposal.match_id == match_id)
        .order_by(MatchProposal.version.desc()).limit(1)
    )


def proposal_response(match: Match, proposal: MatchProposal, member_id: UUID):
    return ProposalResponse(
        id=proposal.id, version=proposal.version, starts_at=proposal.starts_at,
        status=proposal.status, proposed_by_you=proposal.proposed_by_id == member_id,
        contact_enabled=match.status == "confirmed",
    )


async def read(db: AsyncSession, match_id: UUID, member_id: UUID):
    match = await participant_match(db, match_id, member_id)
    proposal = await latest(db, match_id)
    return proposal_response(match, proposal, member_id) if proposal else None


async def propose(db: AsyncSession, match_id: UUID, member_id: UUID, payload: ProposalWrite):
    match = await participant_match(db, match_id, member_id, lock=True)
    if match.status != "pending":
        raise conflict("La coincidencia ya no está pendiente.")
    await get_suggestion(db, member_id, match_id)
    if payload.starts_at <= datetime.now(timezone.utc):
        raise SkillMatchException("El horario debe estar en el futuro.", statuscode=422)
    previous = await latest(db, match_id)
    version = 1
    if previous:
        if previous.id != payload.replaces_proposal_id or previous.status != "pending":
            raise conflict("Revisa la propuesta vigente antes de contraproponer.")
        if previous.proposed_by_id == member_id:
            raise conflict("La otra persona debe responder a tu propuesta.")
        previous.status = "superseded"
        version = previous.version + 1
    elif payload.replaces_proposal_id is not None:
        raise conflict("La propuesta anterior ya no está vigente.")

    proposal = MatchProposal(
        match_id=match_id, proposed_by_id=member_id, version=version,
        starts_at=payload.starts_at, status="pending",
    )
    db.add(proposal)
    # Una propuesta nueva vuelve a mostrar la coincidencia a su destinatario.
    await db.execute(delete(MatchDismissal).where(MatchDismissal.match_id == match_id))
    await db.flush()
    return proposal_response(match, proposal, member_id)


async def decide(db: AsyncSession, match_id: UUID, member_id: UUID, proposal_id: UUID, *, accept: bool):
    match = await participant_match(db, match_id, member_id, lock=True)
    proposal = await latest(db, match_id)
    if proposal is None or proposal.id != proposal_id:
        raise conflict("La propuesta cambió. Revisa el horario vigente.")
    if proposal.proposed_by_id == member_id:
        raise conflict("Solo la otra persona puede responder a esta propuesta.")
    outcome = "accepted" if accept else "declined"
    if proposal.status == outcome:
        return proposal_response(match, proposal, member_id)
    if match.status != "pending" or proposal.status != "pending":
        raise conflict("La propuesta ya fue resuelta.")
    if accept and proposal.starts_at <= datetime.now(timezone.utc):
        raise conflict("Ese horario ya pasó. Envía una contraoferta.")
    if accept:
        await get_suggestion(db, member_id, match_id)
    proposal.status = outcome
    match.status = "confirmed" if accept else "declined"
    await db.flush()
    return proposal_response(match, proposal, member_id)


async def dismiss(db: AsyncSession, match_id: UUID, member_id: UUID):
    match = await participant_match(db, match_id, member_id, lock=True)
    if match.status != "pending" or await latest(db, match_id) is not None:
        raise conflict("Solo puedes descartar una sugerencia sin propuesta.")
    await db.execute(
        insert(MatchDismissal).values(match_id=match_id, member_id=member_id)
        .on_conflict_do_nothing()
    )


async def require_contact(db: AsyncSession, match_id: UUID, member_id: UUID):
    match = await participant_match(db, match_id, member_id)
    if match.status != "confirmed":
        raise conflict("El contacto se habilita al confirmar el intercambio.")


def message_response(message: MatchMessage, member_id: UUID):
    return MessageResponse(
        id=message.id, body=message.body, created_at=message.created_at,
        sent_by_you=message.sender_id == member_id,
    )


async def list_messages(db: AsyncSession, match_id: UUID, member_id: UUID, page: int):
    await require_contact(db, match_id, member_id)
    criteria = MatchMessage.match_id == match_id
    count = await db.scalar(select(func.count()).select_from(MatchMessage).where(criteria))
    messages = await db.scalars(
        select(MatchMessage).where(criteria)
        .order_by(MatchMessage.created_at.desc(), MatchMessage.id.desc())
        .offset((page - 1) * 30).limit(30)
    )
    return [message_response(message, member_id) for message in messages], count or 0


async def send_message(db: AsyncSession, match_id: UUID, member_id: UUID, body: str):
    await require_contact(db, match_id, member_id)
    message = MatchMessage(match_id=match_id, sender_id=member_id, body=body)
    db.add(message)
    await db.flush()
    return message_response(message, member_id)
