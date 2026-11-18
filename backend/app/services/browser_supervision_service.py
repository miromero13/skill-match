"""Owned trial ledger with row-serialized leases and all-or-nothing batches."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.core.exceptions import SkillMatchException
from app.models.browser_supervision import BrowserIncident, BrowserTrial
from app.models.user import User, UserRole

LOCKED = "Esta prueba está activa en otra pestaña o perdió su autorización. Esperá hasta 20 segundos y reintentá."


def utcnow():
    return datetime.now(timezone.utc)


def reject(code, message):
    raise SkillMatchException(statuscode=code, message=message)


class BrowserSupervisionService:
    @staticmethod
    def member(user):
        if user.role != UserRole.MEMBER:
            reject(404, "Recurso no encontrado")

    @classmethod
    async def owned(cls, db, user, trial_id, *, lock=False):
        cls.member(user)
        query = select(BrowserTrial).where(BrowserTrial.id == trial_id, BrowserTrial.user_id == user.id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        trial = (await db.execute(query)).scalar_one_or_none()
        if trial is None:
            reject(404, "Recurso no encontrado")
        return trial

    @staticmethod
    def leased(trial, tab_id, now):
        if (trial.closed_at is not None or trial.expires_at <= now or trial.tab_id != tab_id
                or trial.lease_until is None or trial.lease_until <= now):
            reject(409, LOCKED)

    @classmethod
    async def start(cls, db, user, payload):
        cls.member(user)
        # Serialize creation across all workers, not just this process.
        await db.execute(select(User.id).where(User.id == user.id).with_for_update())
        now = utcnow()
        trial = (await db.execute(select(BrowserTrial).where(
            BrowserTrial.user_id == user.id, BrowserTrial.closed_at.is_(None),
        ).with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()
        if trial is not None and trial.expires_at <= now:
            trial.closed_at = now
            await db.flush()  # Release the partial unique index before inserting.
            trial = None
        if trial is None:
            trial = BrowserTrial(user_id=user.id, created_at=now, expires_at=now + timedelta(hours=24), event_count=0)
            db.add(trial)
        elif trial.tab_id != payload.tab_id and trial.lease_until and trial.lease_until > now:
            reject(409, LOCKED)
        trial.tab_id = payload.tab_id
        trial.lease_until = now + timedelta(seconds=20)
        await db.commit()
        return trial

    @classmethod
    async def action(cls, db, user, trial_id, tab_id, action):
        trial = await cls.owned(db, user, trial_id, lock=True)
        now = utcnow()
        cls.leased(trial, tab_id, now)
        if action == "heartbeat":
            trial.lease_until = now + timedelta(seconds=20)
        else:
            trial.tab_id = None
            trial.lease_until = None
            if action == "close":
                trial.closed_at = now
        await db.commit()
        return trial

    @classmethod
    async def append(cls, db, user, trial_id, payload):
        trial = await cls.owned(db, user, trial_id, lock=True)
        now = utcnow()
        cls.leased(trial, payload.tab_id, now)
        unique = {}
        for event in payload.events:
            if event.event_id in unique and unique[event.event_id] != event:
                reject(409, "Un identificador de incidente ya existe con otro contenido.")
            unique[event.event_id] = event
        stored = (await db.execute(select(BrowserIncident).where(
            BrowserIncident.trial_id == trial.id, BrowserIncident.event_id.in_(unique),
        ))).scalars().all()
        for row in stored:
            proposed = unique[row.event_id]
            if (row.kind != proposed.kind or row.observed_at != proposed.observed_at
                    or row.duration_ms != proposed.duration_ms):
                reject(409, "Un identificador de incidente ya existe con otro contenido.")
        old_ids = {row.event_id for row in stored}
        fresh = [event for key, event in unique.items() if key not in old_ids]
        recent = await db.scalar(select(func.count()).select_from(BrowserIncident).where(
            BrowserIncident.trial_id == trial.id, BrowserIncident.received_at > now - timedelta(minutes=1),
        ))
        if fresh and (recent + len(fresh) > 200 or trial.event_count + len(fresh) > 10_000):
            reject(429, "Límite de incidentes de prueba alcanzado. Esperá antes de reenviar.")
        for event in fresh:
            trial.event_count += 1
            db.add(BrowserIncident(trial_id=trial.id, sequence=trial.event_count, received_at=now,
                                   **event.model_dump()))
        await db.commit()
        return {"accepted_ids": [event.event_id for event in payload.events], "event_count": trial.event_count}

    @classmethod
    async def ledger(cls, db, user, trial_id, after, limit):
        trial = await cls.owned(db, user, trial_id)
        events = (await db.execute(select(BrowserIncident).where(
            BrowserIncident.trial_id == trial.id, BrowserIncident.sequence > after,
        ).order_by(BrowserIncident.sequence).limit(limit))).scalars().all()
        return events, trial.event_count
