"""Session completion service (HU-39).

Coordinates:
- Dual confirmation protocol (RF-SES-07)
- 4-digit presence PIN verification for in-person sessions
- Auditable no-show incident reporting (RF-SES-12)
- Escrow and reputation adapter boundaries (HU-40 / HU-42)
- Notification and audit event emission
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from fastapi import status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import SkillMatchException
from app.models.exchange_session import (
    ExchangeSession,
    SessionAuditEvent,
    SessionConfirmation,
    SessionNoShowReport,
    SessionPresencePin,
)
from app.models.notification import NotificationType
from app.models.user import User
from app.schemas.exchange_session import (
    SessionConfirmRequest,
    SessionConfirmResponse,
    SessionNoShowRequest,
    SessionNoShowResponse,
    SessionPresencePinResponse,
)
from app.services.notification_service import NotificationService
from app.services.session_completion_policy import (
    evaluate_confirmation_transition,
    generate_presence_pin,
    hash_presence_pin,
    verify_presence_pin,
)
from app.services.session_escrow_adapter import SessionEscrowAdapter
from app.services.session_reputation_adapter import SessionReputationAdapter


def _not_found() -> SkillMatchException:
    return SkillMatchException("Recurso no encontrado", statuscode=status.HTTP_404_NOT_FOUND)


def _conflict(message: str) -> SkillMatchException:
    return SkillMatchException(message, statuscode=status.HTTP_409_CONFLICT)


def _unprocessable(message: str) -> SkillMatchException:
    return SkillMatchException(message, statuscode=status.HTTP_422_UNPROCESSABLE_CONTENT)


async def _get_session_for_participant(
    db: AsyncSession,
    session_id: UUID,
    actor_id: UUID,
    *,
    lock: bool = False,
) -> ExchangeSession:
    """Retrieve session ensuring actor is either instructor or learner (404 Obfuscation)."""
    query = select(ExchangeSession).where(
        ExchangeSession.id == session_id,
        or_(
            ExchangeSession.instructor_id == actor_id,
            ExchangeSession.learner_id == actor_id,
        ),
    )
    if lock:
        query = query.with_for_update()

    item = (await db.execute(query)).scalar_one_or_none()
    if item is None:
        raise _not_found()
    return item


async def confirm_session(
    db: AsyncSession,
    actor: User,
    session_id: UUID,
    payload: SessionConfirmRequest,
) -> SessionConfirmResponse:
    """Execute dual confirmation for a session."""
    session = await _get_session_for_participant(db, session_id, actor.id, lock=True)
    now = datetime.now(UTC)
    pin_secret = settings.SECRET_KEY.get_secret_value()
    counterpart_id = (
        session.learner_id if actor.id == session.instructor_id else session.instructor_id
    )

    replay_confirmation = (
        await db.execute(
            select(SessionConfirmation).where(
                SessionConfirmation.session_id == session.id,
                SessionConfirmation.user_id == actor.id,
            )
        )
    ).scalar_one_or_none()
    if replay_confirmation is not None:
        if replay_confirmation.request_key != payload.request_key:
            raise _conflict("Ya has confirmado esta sesión")
        counterpart_replay = (
            await db.execute(
                select(SessionConfirmation).where(
                    SessionConfirmation.session_id == session.id,
                    SessionConfirmation.user_id == counterpart_id,
                )
            )
        ).scalar_one_or_none()
        if session.is_free:
            escrow_status = "NOT_APPLICABLE"
        elif session.payment_state == "RELEASED":
            escrow_status = "RELEASED"
        else:
            escrow_status = "PENDING_HU42"
        return SessionConfirmResponse(
            session_id=session.id,
            status=session.status,
            my_confirmation=True,
            counterpart_confirmation=counterpart_replay is not None,
            actual_minutes=session.actual_minutes or replay_confirmation.actual_minutes,
            completed_at=session.completed_at,
            escrow_release=escrow_status,
        )

    # 1. Validate temporal and lifecycle eligibility before consuming PIN attempts.
    if now < session.ends_at:
        raise _conflict("La sesión todavía no puede confirmarse")

    if session.status != "ACCEPTED":
        raise _conflict("La sesión no admite esta operación")

    # 2. Validate modality and presence PIN rules
    if payload.presence_pin is not None and session.modality == "VIRTUAL":
        raise _unprocessable("El PIN de presencia solo aplica a modalidad presencial")

    if session.modality == "PRESENCIAL":
        if not payload.presence_pin:
            raise _unprocessable("El PIN de presencia es obligatorio para modalidad presencial")

        # In-person session: actor verifies the counterpart's presence PIN
        pin_record = (
            await db.execute(
                select(SessionPresencePin)
                .where(
                    SessionPresencePin.session_id == session.id,
                    SessionPresencePin.user_id == counterpart_id,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()

        if pin_record is None:
            raise _conflict("El PIN de presencia ya no está disponible")

        is_valid, is_locked, err = verify_presence_pin(
            stored_hash=pin_record.pin_hash,
            candidate_pin=payload.presence_pin,
            session_id=session.id,
            user_id=counterpart_id,
            secret=pin_secret,
            attempt_count=pin_record.attempt_count,
            locked_at=pin_record.locked_at,
            expires_at=pin_record.expires_at,
            now=now,
        )

        if is_locked or err == "PIN_LOCKED" or err == "PIN_EXPIRED":
            raise _conflict("El PIN de presencia ya no está disponible")

        if not is_valid:
            pin_record.attempt_count += 1
            if pin_record.attempt_count >= 5:
                pin_record.locked_at = now
            # Persist the security counter before raising: the request dependency
            # rolls back ordinary failures, which must not undo brute-force state.
            await db.commit()
            raise _unprocessable("El PIN de presencia no es válido")

        pin_record.verified_at = now

    # 3. Check existing confirmation by this actor (Idempotency)
    my_confirmation = (
        await db.execute(
            select(SessionConfirmation).where(
                SessionConfirmation.session_id == session.id,
                SessionConfirmation.user_id == actor.id,
            )
        )
    ).scalar_one_or_none()

    counterpart_confirmation = (
        await db.execute(
            select(SessionConfirmation).where(
                SessionConfirmation.session_id == session.id,
                SessionConfirmation.user_id == counterpart_id,
            )
        )
    ).scalar_one_or_none()

    if my_confirmation is not None:
        if my_confirmation.request_key == payload.request_key:
            # Idempotent replay of the exact same request
            escrow_status = (
                "NOT_APPLICABLE"
                if session.is_free
                else await SessionEscrowAdapter.process_completion(
                    session_id=str(session.id),
                    is_free=session.is_free,
                    points_required=session.points_required,
                )
            )
            return SessionConfirmResponse(
                session_id=session.id,
                status=session.status,
                my_confirmation=True,
                counterpart_confirmation=counterpart_confirmation is not None,
                actual_minutes=session.actual_minutes or my_confirmation.actual_minutes,
                completed_at=session.completed_at,
                escrow_release=escrow_status,
            )
        raise _conflict("Ya has confirmado esta sesión")

    # 4. Evaluate transition with counterpart confirmation
    counterpart_dict: dict[str, Any] | None = None
    if counterpart_confirmation is not None:
        counterpart_dict = {"actual_minutes": counterpart_confirmation.actual_minutes}

    can_proceed, reason = evaluate_confirmation_transition(
        session_status=session.status,
        ends_at=session.ends_at,
        existing_confirmation=counterpart_dict,
        new_minutes=payload.actual_minutes,
        now=now,
    )

    if not can_proceed:
        if reason == "MINUTES_MISMATCH":
            raise _conflict("La duración debe coincidir con la confirmación existente")
        raise _conflict("La sesión no admite esta operación")

    # 5. Persist this actor's confirmation
    conf = SessionConfirmation(
        session_id=session.id,
        user_id=actor.id,
        actual_minutes=payload.actual_minutes,
        topics=payload.topics,
        modality=session.modality,
        confirmed_at=now,
        request_key=payload.request_key,
    )
    db.add(conf)

    if reason == "COMPLETED":
        # Atomically complete session
        session.status = "COMPLETED"
        session.actual_minutes = payload.actual_minutes
        session.completed_at = now
        session.completion_version += 1

        escrow_status = await SessionEscrowAdapter.process_completion(
            session_id=str(session.id),
            is_free=session.is_free,
            points_required=session.points_required,
            db=db,
        )

        db.add(
            SessionAuditEvent(
                session_id=session.id,
                actor_id=actor.id,
                event_type="COMPLETED",
                from_status="ACCEPTED",
                to_status="COMPLETED",
                details={
                    "actual_minutes": payload.actual_minutes,
                    "topics": payload.topics,
                    "escrow_release": escrow_status,
                },
            )
        )

        # Notify both participants
        for uid in (session.instructor_id, session.learner_id):
            await NotificationService.emit_in_app(
                db,
                user_id=uid,
                event_id=uuid4(),
                notification_type=NotificationType.SESSION_COMPLETED,
                title="Sesión de intercambio completada",
                message=f"La sesión fue confirmada por ambas partes con una duración de {payload.actual_minutes} minutos.",
            )

        await db.commit()
        return SessionConfirmResponse(
            session_id=session.id,
            status="COMPLETED",
            my_confirmation=True,
            counterpart_confirmation=True,
            actual_minutes=payload.actual_minutes,
            completed_at=now,
            escrow_release=escrow_status,
        )

    # First confirmation recorded
    db.add(
        SessionAuditEvent(
            session_id=session.id,
            actor_id=actor.id,
            event_type="CONFIRMATION_RECORDED",
            from_status="ACCEPTED",
            to_status="ACCEPTED",
            details={
                "actual_minutes": payload.actual_minutes,
                "topics": payload.topics,
            },
        )
    )

    await NotificationService.emit_in_app(
        db,
        user_id=counterpart_id,
        event_id=uuid4(),
        notification_type=NotificationType.SESSION_CONFIRMATION_RECORDED,
        title="Confirmación de sesión recibida",
        message=f"{actor.full_name} confirmó la sesión con una duración de {payload.actual_minutes} minutos. Por favor, confirma para completarla.",
    )

    await db.commit()
    return SessionConfirmResponse(
        session_id=session.id,
        status="ACCEPTED",
        my_confirmation=True,
        counterpart_confirmation=False,
        actual_minutes=payload.actual_minutes,
        completed_at=None,
        escrow_release="NOT_APPLICABLE",
    )


async def report_noshow(
    db: AsyncSession,
    actor: User,
    session_id: UUID,
    payload: SessionNoShowRequest,
) -> SessionNoShowResponse:
    """Report no-show for a session."""
    session = await _get_session_for_participant(db, session_id, actor.id, lock=True)
    now = datetime.now(UTC)

    if now < session.ends_at:
        raise _conflict("La sesión todavía no ha finalizado")

    if session.status != "ACCEPTED":
        raise _conflict("La sesión no admite esta operación")

    counterpart_id = (
        session.learner_id if actor.id == session.instructor_id else session.instructor_id
    )

    # If counterpart already confirmed, they were present -> conflict
    counterpart_confirmation = (
        await db.execute(
            select(SessionConfirmation).where(
                SessionConfirmation.session_id == session.id,
                SessionConfirmation.user_id == counterpart_id,
            )
        )
    ).scalar_one_or_none()

    if counterpart_confirmation is not None:
        raise _conflict("No puedes reportar inasistencia si la contraparte ya confirmó la sesión")

    # Check if report already exists
    existing = (
        await db.execute(
            select(SessionNoShowReport).where(
                SessionNoShowReport.session_id == session.id,
                SessionNoShowReport.absent_user_id == counterpart_id,
            )
        )
    ).scalar_one_or_none()

    if existing is not None:
        if existing.request_key == payload.request_key:
            return SessionNoShowResponse(
                session_id=session.id,
                reported_by_id=existing.reported_by_id,
                absent_user_id=existing.absent_user_id,
                reason=existing.reason,
                status=existing.status,
                reported_at=existing.reported_at,
            )
        raise _conflict("Ya se registró un reporte de inasistencia para esta sesión")

    contradictory = (
        await db.execute(
            select(SessionNoShowReport).where(
                SessionNoShowReport.session_id == session.id,
                SessionNoShowReport.reported_by_id == counterpart_id,
                SessionNoShowReport.absent_user_id == actor.id,
            )
        )
    ).scalar_one_or_none()
    if contradictory is not None:
        raise _conflict("La sesión ya tiene un reporte de inasistencia contradictorio")

    incident_status = await SessionReputationAdapter.record_noshow_incident(
        db=db,
        session_id=session.id,
        absent_user_id=counterpart_id,
        reported_by_id=actor.id,
    )

    report = SessionNoShowReport(
        session_id=session.id,
        reported_by_id=actor.id,
        absent_user_id=counterpart_id,
        reason=payload.reason,
        status=incident_status,
        reported_at=now,
        request_key=payload.request_key,
    )
    db.add(report)

    db.add(
        SessionAuditEvent(
            session_id=session.id,
            actor_id=actor.id,
            event_type="NO_SHOW_REPORTED",
            from_status=session.status,
            to_status=session.status,
            details={
                "absent_user_id": str(counterpart_id),
                "reason": payload.reason,
            },
        )
    )

    await NotificationService.emit_in_app(
        db,
        user_id=counterpart_id,
        event_id=uuid4(),
        notification_type=NotificationType.SESSION_NO_SHOW_REPORTED,
        title="Reporte de inasistencia recibido",
        message=f"Se ha registrado un reporte de inasistencia para tu sesión del {session.starts_at.strftime('%Y-%m-%d %H:%M')}.",
    )

    await db.commit()
    return SessionNoShowResponse(
        session_id=session.id,
        reported_by_id=actor.id,
        absent_user_id=counterpart_id,
        reason=payload.reason,
        status=incident_status,
        reported_at=now,
    )


async def get_or_create_presence_pin(
    db: AsyncSession,
    actor: User,
    session_id: UUID,
) -> SessionPresencePinResponse:
    """Retrieve or create the presence PIN for an in-person session participant."""
    session = await _get_session_for_participant(db, session_id, actor.id, lock=True)

    if session.modality != "PRESENCIAL":
        raise _unprocessable("El PIN de presencia solo aplica a modalidad presencial")

    now = datetime.now(UTC)
    pin_secret = settings.SECRET_KEY.get_secret_value()
    pin_record = (
        await db.execute(
            select(SessionPresencePin).where(
                SessionPresencePin.session_id == session.id,
                SessionPresencePin.user_id == actor.id,
            )
        )
    ).scalar_one_or_none()

    if pin_record is None:
        pin = generate_presence_pin(
            session_id=session.id,
            user_id=actor.id,
            secret=pin_secret,
        )
        pin_record = SessionPresencePin(
            session_id=session.id,
            user_id=actor.id,
            pin_hash=hash_presence_pin(
                pin,
                session_id=session.id,
                user_id=actor.id,
                secret=pin_secret,
            ),
            attempt_count=0,
            expires_at=session.ends_at + timedelta(hours=24),
            created_at=now,
        )
        db.add(pin_record)
        await db.commit()
        return SessionPresencePinResponse(
            session_id=session.id,
            presence_pin=pin,
            expires_at=pin_record.expires_at,
            attempt_count=0,
            is_locked=False,
        )

    pin = generate_presence_pin(
        session_id=session.id,
        user_id=actor.id,
        secret=pin_secret,
    )
    return SessionPresencePinResponse(
        session_id=session.id,
        presence_pin=pin,
        expires_at=pin_record.expires_at,
        attempt_count=pin_record.attempt_count,
        is_locked=pin_record.locked_at is not None or pin_record.attempt_count >= 5,
    )
