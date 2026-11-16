from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import SkillMatchException
from app.football.config import load_football_config
from app.football.models import (
    ChallengeSegment,
    FraudIncident,
    ValidationSession,
    ValidationSessionState,
)
from app.football.pipeline.challenge_engine import generate_plan


async def count_recent_attempts(
    db: AsyncSession,
    user_id: UUID,
    skill_id: UUID | None,
    window_minutes: int,
) -> int:
    cutoff = datetime.now(UTC) - timedelta(minutes=window_minutes)
    stmt = select(func.count(ValidationSession.id)).where(
        ValidationSession.user_id == user_id,
        ValidationSession.creada_en >= cutoff,
    )
    if skill_id is not None:
        stmt = stmt.where(ValidationSession.skill_id == skill_id)
    result = await db.execute(stmt)
    return int(result.scalar_one() or 0)


async def create_validation_session(
    db: AsyncSession,
    user_id: UUID,
    skill_id: UUID | None = None,
    route_prefix: str = "/api/football",
) -> tuple[ValidationSession, int, str]:
    """
    Create a new Football ValidationSession enforcing attempt limits and cooldown window.
    Returns `(session, remaining_attempts, ws_url)`.
    """
    cfg = load_football_config()
    max_attempts = cfg.session.max_attempts_per_window
    cooldown_minutes = cfg.session.cooldown_minutes

    recent_count = await count_recent_attempts(
        db=db,
        user_id=user_id,
        skill_id=skill_id,
        window_minutes=cooldown_minutes,
    )
    if recent_count >= max_attempts:
        raise SkillMatchException(
            statuscode=status.HTTP_429_TOO_MANY_REQUESTS,
            message=(
                f"Has alcanzado el límite de {max_attempts} intentos. "
                f"Por favor espera {cooldown_minutes} minutos antes de volver a intentarlo."
            ),
        )

    seed = secrets.randbelow(2_000_000_000) + 1
    segments_plan, signed_plan = generate_plan(seed)
    now = datetime.now(UTC)

    session_obj = ValidationSession(
        user_id=user_id,
        skill_id=skill_id,
        estado=ValidationSessionState.CREATED.value,
        semilla=seed,
        plan_firmado=signed_plan,
        creada_en=now,
        version_modelo="rules-v1",
        version_config=f"{cfg.version}:{cfg.config_hash[:12]}",
    )
    db.add(session_obj)
    await db.flush()

    for seg in segments_plan:
        db.add(
            ChallengeSegment(
                session_id=session_obj.id,
                indice=int(seg["indice"]),
                tipo=str(seg["tipo"]),
                inicio_servidor_ms=int(seg["inicio_servidor_ms"]),
                duracion_ms=int(seg["duracion_ms"]),
            )
        )

    await db.commit()
    await db.refresh(session_obj)

    remaining = max(0, max_attempts - (recent_count + 1))
    ws_url = f"{route_prefix}/sessions/{session_obj.id}/ws"
    return session_obj, remaining, ws_url


async def get_Owned_validation_session(
    db: AsyncSession,
    session_id: UUID,
    user_id: UUID,
) -> ValidationSession:
    """Fetch a ValidationSession with segments and verify ownership by `user_id`."""
    stmt = (
        select(ValidationSession)
        .options(selectinload(ValidationSession.segments))
        .where(ValidationSession.id == session_id)
    )
    result = await db.execute(stmt)
    session_obj = result.scalar_one_or_none()
    if session_obj is None or session_obj.user_id != user_id:
        raise SkillMatchException(
            statuscode=status.HTTP_404_NOT_FOUND,
            message="Sesión de validación no encontrada.",
        )
    return session_obj


async def record_client_event_incident(
    db: AsyncSession,
    session_id: UUID,
    event_type: str,
    timestamp_ms: int,
) -> FraudIncident:
    """Persist a client-side anti-fraud event (`tab_hidden`, `focus_lost`, `fullscreen_exit`)."""
    incident = FraudIncident(
        session_id=session_id,
        tipo=event_type,
        severidad="medium",
        t_ms=max(0, timestamp_ms),
        detalle=f"Evento de cliente reportado por WebSocket: {event_type}",
    )
    db.add(incident)
    await db.commit()
    await db.refresh(incident)
    return incident
