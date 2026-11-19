from datetime import UTC, datetime, time, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import SkillMatchException
from app.models.catalog import Skill
from app.models.exchange_session import (
    BookingRestriction,
    ExchangeSession,
    SessionAuditEvent,
    SessionCancellation,
    SessionQuotaMovement,
    WeeklySessionQuota,
)
from app.models.match import Match
from app.models.notification import NotificationType
from app.models.teaching_skill import TeachingSkill
from app.models.user import User
from app.models.user_availability import UserAvailability
from app.models.user_block import UserBlock
from app.models.user_learning_skill import UserLearningSkill
from app.schemas.exchange_session import (
    ExchangeSessionCreate,
    ExchangeSessionReschedule,
    ExchangeSessionResponse,
    SessionCalendarExportResponse,
)
from app.schemas.match import (
    CommonSessionSlot,
    MatchSessionOptionsResponse,
    SessionBookingDirection,
)
from app.services.exchange_session_policy import (
    classify_cancellation,
    local_month_bounds,
    local_week_bounds,
)
from app.services.notification_service import NotificationService
from app.services.session_calendar_service import build_ics_export, is_calendar_export_allowed

ACTIVE_STATUSES = ("PENDING", "ACCEPTED")
FREE_LIMIT = 2
SESSION_OPTIONS_HORIZON_DAYS = 14


def _conflict(message: str) -> SkillMatchException:
    return SkillMatchException(message, statuscode=status.HTTP_409_CONFLICT)


def _not_found() -> SkillMatchException:
    return SkillMatchException("Recurso no encontrado", statuscode=status.HTTP_404_NOT_FOUND)


async def _get_session_for_member(
    db: AsyncSession,
    session_id: UUID,
    actor_id: UUID,
    *,
    lock: bool = False,
) -> ExchangeSession:
    query = select(ExchangeSession).where(
        ExchangeSession.id == session_id,
        or_(ExchangeSession.instructor_id == actor_id, ExchangeSession.learner_id == actor_id),
    )
    if lock:
        query = query.with_for_update()
    item = (await db.execute(query)).scalar_one_or_none()
    if item is None:
        raise _not_found()
    return item


async def _active_booking_block(db: AsyncSession, user_id: UUID) -> datetime | None:
    return (
        await db.execute(
            select(func.max(BookingRestriction.ends_at)).where(
                BookingRestriction.user_id == user_id,
                BookingRestriction.ends_at > datetime.now(UTC),
            )
        )
    ).scalar_one_or_none()


async def _assert_can_book(db: AsyncSession, actor_id: UUID) -> None:
    blocked_until = await _active_booking_block(db, actor_id)
    if blocked_until is not None:
        raise _conflict(f"No puedes agendar sesiones hasta {blocked_until.isoformat()}.")


def _ceil_to_half_hour(value: datetime, timezone: str) -> datetime:
    local = value.astimezone(ZoneInfo(timezone)).replace(second=0, microsecond=0)
    remainder = local.minute % 30
    if remainder:
        local += timedelta(minutes=30 - remainder)
    elif local <= value.astimezone(ZoneInfo(timezone)):
        local += timedelta(minutes=30)
    return local.astimezone(UTC)


def _overlaps_active_session(
    existing: list[ExchangeSession],
    buffers: dict[UUID, int],
    starts_at: datetime,
    ends_at: datetime,
) -> bool:
    for item in existing:
        shared = {item.instructor_id, item.learner_id} & set(buffers)
        buffer_minutes = max((buffers[user_id] for user_id in shared), default=0)
        if (
            item.starts_at < ends_at + timedelta(minutes=buffer_minutes)
            and item.ends_at + timedelta(minutes=buffer_minutes) > starts_at
        ):
            return True
    return False


async def get_match_session_options(
    db: AsyncSession,
    actor: User,
    match_id: UUID,
) -> MatchSessionOptionsResponse:
    """Return only authorized, currently bookable directions and common slots."""
    match = await db.get(Match, match_id)
    if match is None or actor.id not in (match.member_a_id, match.member_b_id):
        raise _not_found()
    if match.status.lower() != "confirmed":
        raise _conflict("La coincidencia debe estar confirmada antes de consultar horarios.")

    participant_ids = [match.member_a_id, match.member_b_id]
    users = list((await db.scalars(select(User).where(User.id.in_(participant_ids)))).all())
    by_id = {user.id: user for user in users}
    if len(by_id) != 2:
        raise _not_found()

    bilateral = await db.scalar(
        select(UserBlock.id).where(
            or_(
                and_(UserBlock.blocker_id == participant_ids[0], UserBlock.blocked_id == participant_ids[1]),
                and_(UserBlock.blocker_id == participant_ids[1], UserBlock.blocked_id == participant_ids[0]),
            )
        )
    )
    if bilateral is not None:
        raise _conflict("No es posible agendar con este miembro.")

    availability = list(
        (
            await db.scalars(
                select(UserAvailability).where(
                    UserAvailability.user_id.in_(participant_ids),
                    UserAvailability.is_enabled.is_(True),
                )
            )
        ).all()
    )
    existing = list(
        (
            await db.scalars(
                select(ExchangeSession).where(
                    ExchangeSession.status.in_(ACTIVE_STATUSES),
                    or_(
                        ExchangeSession.instructor_id.in_(participant_ids),
                        ExchangeSession.learner_id.in_(participant_ids),
                    ),
                )
            )
        ).all()
    )
    buffers = {user.id: user.buffer_minutes for user in users}
    display_timezone = actor.timezone
    first_start = _ceil_to_half_hour(datetime.now(UTC), display_timezone)
    horizon = datetime.now(UTC) + timedelta(days=SESSION_OPTIONS_HORIZON_DAYS)
    directions: list[SessionBookingDirection] = []

    for instructor_id in participant_ids:
        learner_id = participant_ids[1] if instructor_id == participant_ids[0] else participant_ids[0]
        rows = (
            await db.execute(
                select(TeachingSkill, Skill.name)
                .join(Skill, Skill.id == TeachingSkill.skill_id)
                .join(
                    UserLearningSkill,
                    and_(
                        UserLearningSkill.skill_id == TeachingSkill.skill_id,
                        UserLearningSkill.user_id == learner_id,
                    ),
                )
                .where(TeachingSkill.user_id == instructor_id)
                .order_by(Skill.name, TeachingSkill.id)
            )
        ).all()
        for offer, skill_name in rows:
            slots: list[CommonSessionSlot] = []
            modalities: set[str] = set()
            starts_at = first_start
            while starts_at < horizon:
                for modality in ("VIRTUAL", "PRESENCIAL"):
                    for duration in (30, 60):
                        ends_at = starts_at + timedelta(minutes=duration)
                        if ends_at > horizon:
                            continue
                        fits_both = all(
                            any(
                                slot.user_id == user.id
                                and _fits_slot(starts_at, ends_at, user, slot, modality)
                                for slot in availability
                            )
                            for user in (by_id[instructor_id], by_id[learner_id])
                        )
                        if not fits_both or _overlaps_active_session(
                            existing, buffers, starts_at, ends_at
                        ):
                            continue
                        modalities.add(modality)
                        slots.append(
                            CommonSessionSlot(
                                starts_at=starts_at,
                                ends_at=ends_at,
                                timezone=display_timezone,
                                modality=modality,
                                duration_minutes=duration,
                            )
                        )
                starts_at += timedelta(minutes=30)
            directions.append(
                SessionBookingDirection(
                    instructor_id=instructor_id,
                    instructor_name=by_id[instructor_id].full_name,
                    learner_id=learner_id,
                    teaching_skill_id=offer.id,
                    skill_name=skill_name,
                    modalities=sorted(modalities),
                    common_slots=slots,
                )
            )

    return MatchSessionOptionsResponse(
        match_id=match.id,
        timezone=display_timezone,
        booking_blocked_until=await _active_booking_block(db, actor.id),
        directions=directions,
    )


async def _resolve_context(
    db: AsyncSession,
    actor_id: UUID,
    payload: ExchangeSessionCreate,
) -> tuple[Match, User, User, TeachingSkill]:
    match = (
        await db.execute(select(Match).where(Match.id == payload.match_id))
    ).scalar_one_or_none()
    if match is None or actor_id not in (match.member_a_id, match.member_b_id):
        raise _not_found()
    if match.status.lower() != "confirmed":
        raise _conflict("La coincidencia debe estar confirmada antes de agendar.")
    if payload.instructor_id not in (match.member_a_id, match.member_b_id):
        raise _conflict("El instructor no pertenece a la coincidencia.")
    learner_id = (
        match.member_b_id if payload.instructor_id == match.member_a_id else match.member_a_id
    )
    users = (
        (await db.execute(select(User).where(User.id.in_([payload.instructor_id, learner_id]))))
        .scalars()
        .all()
    )
    by_id = {user.id: user for user in users}
    if len(by_id) != 2:
        raise _conflict("Los participantes de la sesión no están disponibles.")
    instructor, learner = by_id[payload.instructor_id], by_id[learner_id]
    offer = (
        await db.execute(
            select(TeachingSkill).where(
                TeachingSkill.id == payload.teaching_skill_id,
                TeachingSkill.user_id == instructor.id,
            )
        )
    ).scalar_one_or_none()
    if offer is None:
        raise _conflict("La habilidad seleccionada no pertenece al instructor.")
    bilateral = (
        await db.execute(
            select(UserBlock.id).where(
                or_(
                    and_(UserBlock.blocker_id == instructor.id, UserBlock.blocked_id == learner.id),
                    and_(UserBlock.blocker_id == learner.id, UserBlock.blocked_id == instructor.id),
                )
            )
        )
    ).scalar_one_or_none()
    if bilateral is not None:
        raise _conflict("No es posible agendar con este miembro.")
    return match, instructor, learner, offer


def _fits_slot(
    start: datetime, end: datetime, user: User, slot: UserAvailability, modality: str
) -> bool:
    zone = ZoneInfo(user.timezone)
    local_start, local_end = start.astimezone(zone), end.astimezone(zone)
    if local_start.date() != local_end.date() or local_start.weekday() != slot.day_of_week:
        return False
    slot_start = time.fromisoformat(slot.start_time)
    slot_end = time.fromisoformat(slot.end_time)
    return (
        slot.is_enabled
        and slot.modality in ("BOTH", modality)
        and local_start.time().replace(tzinfo=None) >= slot_start
        and local_end.time().replace(tzinfo=None) <= slot_end
    )


async def _assert_schedule(
    db: AsyncSession,
    instructor: User,
    learner: User,
    starts_at: datetime,
    ends_at: datetime,
    modality: str,
    *,
    exclude_session_id: UUID | None = None,
) -> None:
    if starts_at <= datetime.now(UTC):
        raise _conflict("La sesión debe programarse en una fecha futura.")
    slots = (
        (
            await db.execute(
                select(UserAvailability).where(
                    UserAvailability.user_id.in_([instructor.id, learner.id]),
                    UserAvailability.is_enabled.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    for user in (instructor, learner):
        if not any(
            slot.user_id == user.id and _fits_slot(starts_at, ends_at, user, slot, modality)
            for slot in slots
        ):
            raise _conflict("El horario no está dentro de la disponibilidad común.")

    query = select(ExchangeSession).where(
        ExchangeSession.status.in_(ACTIVE_STATUSES),
        or_(
            ExchangeSession.instructor_id.in_([instructor.id, learner.id]),
            ExchangeSession.learner_id.in_([instructor.id, learner.id]),
        ),
    )
    if exclude_session_id is not None:
        query = query.where(ExchangeSession.id != exclude_session_id)
    existing = (await db.execute(query)).scalars().all()
    buffers = {instructor.id: instructor.buffer_minutes, learner.id: learner.buffer_minutes}
    for item in existing:
        shared = {item.instructor_id, item.learner_id} & set(buffers)
        buffer_minutes = max((buffers[user_id] for user_id in shared), default=0)
        from datetime import timedelta

        if (
            item.starts_at < ends_at + timedelta(minutes=buffer_minutes)
            and item.ends_at + timedelta(minutes=buffer_minutes) > starts_at
        ):
            raise _conflict("El horario se superpone con otra sesión o su tiempo de descanso.")


async def _locked_quota(
    db: AsyncSession,
    learner: User,
    starts_at: datetime,
) -> WeeklySessionQuota:
    week_start = (
        local_week_bounds(starts_at, learner.timezone)[0]
        .astimezone(ZoneInfo(learner.timezone))
        .date()
    )
    await db.execute(
        insert(WeeklySessionQuota)
        .values(
            user_id=learner.id,
            week_start=week_start,
            used=0,
            version=1,
        )
        .on_conflict_do_nothing(index_elements=["user_id", "week_start"])
    )
    quota = (
        await db.execute(
            select(WeeklySessionQuota)
            .where(
                WeeklySessionQuota.user_id == learner.id,
                WeeklySessionQuota.week_start == week_start,
            )
            .with_for_update()
        )
    ).scalar_one()
    return quota


async def _reserve_quota(
    db: AsyncSession, learner: User, starts_at: datetime
) -> WeeklySessionQuota:
    quota = await _locked_quota(db, learner, starts_at)
    if quota.used >= FREE_LIMIT:
        raise _conflict(
            "No tienes sesiones gratuitas disponibles; el pago requiere HU-42 y aún no está disponible."
        )
    quota.used += 1
    quota.version += 1
    return quota


async def _release_quota(
    db: AsyncSession,
    item: ExchangeSession,
    learner: User,
    *,
    kind: str,
) -> None:
    quota = await _locked_quota(db, learner, item.starts_at)
    if quota.used > 0:
        quota.used -= 1
        quota.version += 1
        db.add(SessionQuotaMovement(quota_id=quota.id, session_id=item.id, kind=kind, delta=-1))


def _audit(
    item: ExchangeSession, actor_id: UUID, event_type: str, **details: object
) -> SessionAuditEvent:
    return SessionAuditEvent(
        session_id=item.id,
        actor_id=actor_id,
        event_type=event_type,
        details=details,
    )


async def _notify_counterpart(
    db: AsyncSession,
    item: ExchangeSession,
    actor_id: UUID,
    notification_type: NotificationType,
    title: str,
    message: str,
) -> None:
    recipient_id = item.learner_id if actor_id == item.instructor_id else item.instructor_id
    await NotificationService.emit_in_app(
        db,
        user_id=recipient_id,
        event_id=uuid4(),
        notification_type=notification_type,
        title=title,
        message=message,
    )


async def _response(db: AsyncSession, item: ExchangeSession) -> ExchangeSessionResponse:
    payload = ExchangeSessionResponse.model_validate(item).model_dump()
    payload["booking_blocked_until"] = (
        await _active_booking_block(db, item.cancelled_by_id) if item.cancelled_by_id else None
    )
    return ExchangeSessionResponse.model_validate(payload)


async def get_calendar_export(
    db: AsyncSession,
    actor_id: UUID,
    session_id: UUID,
) -> SessionCalendarExportResponse:
    item = await _get_session_for_member(db, session_id, actor_id)
    if not is_calendar_export_allowed(item.status):
        raise _conflict("Solo las sesiones aceptadas se pueden exportar al calendario.")
    skill_name = await db.scalar(
        select(Skill.name)
        .join(TeachingSkill, TeachingSkill.skill_id == Skill.id)
        .where(TeachingSkill.id == item.teaching_skill_id)
    )
    counterpart_id = item.learner_id if actor_id == item.instructor_id else item.instructor_id
    counterpart_name = await db.scalar(select(User.full_name).where(User.id == counterpart_id))
    if skill_name is None or counterpart_name is None:
        raise _not_found()
    result = build_ics_export(
        session_id=item.id,
        starts_at=item.starts_at,
        ends_at=item.ends_at,
        timezone=item.timezone,
        skill_name=skill_name,
        counterpart_name=counterpart_name,
        modality=item.modality,
    )
    return SessionCalendarExportResponse.model_validate(result, from_attributes=True)


async def create(
    db: AsyncSession, actor_id: UUID, payload: ExchangeSessionCreate
) -> ExchangeSessionResponse:
    await _assert_can_book(db, actor_id)
    match, instructor, learner, _ = await _resolve_context(db, actor_id, payload)
    await _assert_schedule(
        db, instructor, learner, payload.starts_at, payload.ends_at, payload.modality
    )
    quota = await _reserve_quota(db, learner, payload.starts_at)
    item = ExchangeSession(
        match_id=match.id,
        teaching_skill_id=payload.teaching_skill_id,
        created_by_id=actor_id,
        instructor_id=instructor.id,
        learner_id=learner.id,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        timezone=payload.timezone,
        modality=payload.modality,
        status="PENDING",
    )
    db.add(item)
    await db.flush()
    db.add_all(
        [
            SessionQuotaMovement(quota_id=quota.id, session_id=item.id, kind="RESERVED", delta=1),
            _audit(item, actor_id, "CREATED"),
            _audit(item, actor_id, "QUOTA_RESERVED", quota_id=str(quota.id)),
        ]
    )
    await _notify_counterpart(
        db,
        item,
        actor_id,
        NotificationType.SESSION_PROPOSED,
        "Nueva propuesta de sesión",
        "Recibiste una propuesta de sesión de intercambio.",
    )
    await db.flush()
    return await _response(db, item)


async def list_for_member(
    db: AsyncSession,
    actor: User,
    page: int,
    page_size: int,
) -> tuple[list[ExchangeSessionResponse], int, int]:
    predicate = or_(
        ExchangeSession.instructor_id == actor.id, ExchangeSession.learner_id == actor.id
    )
    total = (
        await db.execute(select(func.count()).select_from(ExchangeSession).where(predicate))
    ).scalar_one()
    rows = (
        (
            await db.execute(
                select(ExchangeSession)
                .where(predicate)
                .order_by(
                    ExchangeSession.starts_at.desc(),
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    week_start = (
        local_week_bounds(datetime.now(UTC), actor.timezone)[0]
        .astimezone(ZoneInfo(actor.timezone))
        .date()
    )
    used = (
        await db.execute(
            select(WeeklySessionQuota.used).where(
                WeeklySessionQuota.user_id == actor.id,
                WeeklySessionQuota.week_start == week_start,
            )
        )
    ).scalar_one_or_none() or 0
    return [await _response(db, row) for row in rows], total, max(0, FREE_LIMIT - used)


async def update_status(
    db: AsyncSession,
    actor_id: UUID,
    session_id: UUID,
    new_status: str,
) -> ExchangeSessionResponse:
    item = await _get_session_for_member(db, session_id, actor_id, lock=True)
    if actor_id == item.created_by_id:
        raise _conflict("Solo la contraparte del proponente puede responder.")
    if item.status == new_status:
        return await _response(db, item)
    if item.status != "PENDING":
        raise _conflict("La sesión ya no admite esta transición.")
    old = item.status
    item.status = new_status
    db.add(_audit(item, actor_id, new_status, from_status=old, to_status=new_status))
    if new_status == "REJECTED":
        learner = await db.get(User, item.learner_id)
        await _release_quota(db, item, learner, kind="RELEASED")
        db.add(_audit(item, actor_id, "QUOTA_RELEASED"))
    notification_type = (
        NotificationType.SESSION_ACCEPTED
        if new_status == "ACCEPTED"
        else NotificationType.SESSION_REJECTED
    )
    await _notify_counterpart(
        db,
        item,
        actor_id,
        notification_type,
        "Propuesta de sesión actualizada",
        f"Tu propuesta de sesión fue {new_status.lower()}.",
    )
    await db.flush()
    return await _response(db, item)


async def reschedule(
    db: AsyncSession,
    actor_id: UUID,
    session_id: UUID,
    payload: ExchangeSessionReschedule,
) -> ExchangeSessionResponse:
    await _assert_can_book(db, actor_id)
    item = await _get_session_for_member(db, session_id, actor_id, lock=True)
    if item.status not in ACTIVE_STATUSES:
        raise _conflict("La sesión ya no puede reprogramarse.")
    if item.status == "PENDING" and (
        item.starts_at == payload.starts_at and item.ends_at == payload.ends_at
    ):
        return await _response(db, item)
    instructor, learner = (
        await db.get(User, item.instructor_id),
        await db.get(User, item.learner_id),
    )
    await _assert_schedule(
        db,
        instructor,
        learner,
        payload.starts_at,
        payload.ends_at,
        item.modality,
        exclude_session_id=item.id,
    )
    old_week = local_week_bounds(item.starts_at, learner.timezone)[0]
    new_week = local_week_bounds(payload.starts_at, learner.timezone)[0]
    if old_week != new_week:
        await _release_quota(db, item, learner, kind="RELEASED")
        new_quota = await _reserve_quota(db, learner, payload.starts_at)
        db.add(
            SessionQuotaMovement(
                quota_id=new_quota.id, session_id=item.id, kind="RESERVED", delta=1
            )
        )
    old_start = item.starts_at
    item.starts_at, item.ends_at, item.status = payload.starts_at, payload.ends_at, "PENDING"
    db.add(_audit(item, actor_id, "RESCHEDULED", old_starts_at=old_start.isoformat()))
    await _notify_counterpart(
        db,
        item,
        actor_id,
        NotificationType.SESSION_RESCHEDULED,
        "Sesión reprogramada",
        "La fecha de una sesión fue reprogramada y requiere nueva aceptación.",
    )
    await db.flush()
    return await _response(db, item)


async def cancel(
    db: AsyncSession,
    actor: User,
    session_id: UUID,
    reason: str,
) -> ExchangeSessionResponse:
    item = await _get_session_for_member(db, session_id, actor.id, lock=True)
    if item.status == "CANCELLED":
        return await _response(db, item)
    if item.status == "REJECTED":
        raise _conflict("Una sesión rechazada no puede cancelarse.")
    now = datetime.now(UTC)
    month_start, next_month = local_month_bounds(now, actor.timezone)
    prior = (
        await db.execute(
            select(func.count())
            .select_from(SessionCancellation)
            .where(
                SessionCancellation.cancelled_by_id == actor.id,
                SessionCancellation.cancelled_at >= month_start,
                SessionCancellation.cancelled_at < next_month,
            )
        )
    ).scalar_one()
    decision = classify_cancellation(
        starts_at=item.starts_at,
        cancelled_at=now,
        actor_monthly_cancellations=prior,
    )
    if decision.restore_quota:
        learner = await db.get(User, item.learner_id)
        await _release_quota(db, item, learner, kind="RESTORED")
        item.quota_restored = True
        db.add(_audit(item, actor.id, "QUOTA_RESTORED"))
    item.status = "CANCELLED"
    item.cancellation_reason = reason
    item.cancelled_by_id = actor.id
    item.cancelled_at = now
    db.add(
        SessionCancellation(
            session_id=item.id,
            cancelled_by_id=actor.id,
            reason=reason,
            cancelled_at=now,
            is_timely=decision.is_timely,
            quota_restored=item.quota_restored,
            triggers_booking_block=decision.blocks_booking,
        )
    )
    db.add(_audit(item, actor.id, "CANCELLED", is_timely=decision.is_timely))
    if decision.blocks_booking and decision.booking_blocked_until is not None:
        block_reason = "LATE_CANCELLATION" if not decision.is_timely else "MONTHLY_CANCELLATIONS"
        db.add(
            BookingRestriction(
                user_id=actor.id,
                source_session_id=item.id,
                reason=block_reason,
                starts_at=now,
                ends_at=decision.booking_blocked_until,
            )
        )
        db.add(
            _audit(
                item, actor.id, "BOOKING_BLOCKED", until=decision.booking_blocked_until.isoformat()
            )
        )
    await _notify_counterpart(
        db,
        item,
        actor.id,
        NotificationType.SESSION_CANCELLED,
        "Sesión cancelada",
        "La contraparte canceló una sesión de intercambio.",
    )
    await db.flush()
    return await _response(db, item)
