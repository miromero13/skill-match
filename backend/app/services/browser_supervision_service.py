"""Owned trial ledger with row-serialized leases and all-or-nothing batches."""
import asyncio
import functools
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import get_args

from sqlalchemy import func, select

from app.core.exceptions import SkillMatchException
from app.models.browser_supervision import BrowserIncident, BrowserTrial
from app.models.user import User, UserRole
from app.schemas.browser_supervision import (
    AVWindowRequest, GazeCalibrationRequest, IncidentKind, IncidentResponse,
)
from app.services.continuous_supervision_service import ContinuousSupervisionService
from app.services.integrity.gaze import GazeCalibrationError, compute_zone

LOCKED = "Esta prueba está activa en otra pestaña o perdió su autorización. Esperá hasta 20 segundos y reintentá."
DEFAULT_CADENCE_MS = 2400  # expected spacing of audiovisual windows when the client does not say
GAP_FACTOR = 3  # no window for more than this many cadences while the lease is active is a gap
MAX_DURATION_MS = 86_400_000
BROWSER_EVENTS_PER_MINUTE = 200
BROWSER_EVENTS_PER_TRIAL = 10_000
AV_ROWS_PER_MINUTE = 120
AV_ROWS_PER_TRIAL = 5_000
AV_INFERENCE_WORKERS = 2

# Kinds produced by server-side audiovisual analysis; every other kind is browser-reported.
AV_KINDS = (
    "FACE_ABSENT", "MULTIPLE_FACES", "IDENTITY_MISMATCH", "HEAD_POSE_DOWN", "HEAD_POSE_SIDE", "HEAD_POSE_UP",
    "GAZE_AWAY", "CLIENT_MISMATCH", "VOICE_DETECTED", "MULTIPLE_SPEAKERS", "HIGH_NOISE", "MODEL_UNAVAILABLE",
    "VIDEO_MISSING", "AUDIO_MISSING", "WINDOW_GAP", "FACE_OCCLUDED", "MOUTH_OCCLUDED", "CAMERA_BLOCKED",
)
BROWSER_KINDS = tuple(kind for kind in get_args(IncidentKind) if kind not in AV_KINDS)

# Calibration failures: code -> (HTTP status, message shown verbatim by the frontend).
GAZE_CALIBRATION_ERRORS = {
    "FACE_MISSING": (400, "No pudimos ver tu rostro en todos los puntos. Ubicate frente a la cámara con buena luz "
                          "y repetí la calibración."),
    "MULTIPLE_FACES": (400, "Se detectó más de una persona durante la calibración. Tiene que estar solo tu rostro "
                            "en cámara."),
    "NOT_DISTINGUISHABLE": (400, "No pudimos distinguir hacia dónde mirabas. Mirá cada punto moviendo los ojos o la "
                                 "cabeza hacia esa esquina y repetí la calibración."),
    "MODEL_UNAVAILABLE": (503, "El análisis de mirada no está disponible en este momento. Reintentá más tarde."),
}

# Bounded pool: inference is CPU-heavy and native models are shared, so only a few run at once.
_AV_EXECUTOR = ThreadPoolExecutor(max_workers=AV_INFERENCE_WORKERS, thread_name_prefix="av-inference")


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
            since = cls.gap_since(trial, now, DEFAULT_CADENCE_MS)
            if since is not None:
                await cls.record_gap(db, trial, since, now)
        else:
            trial.tab_id = None
            trial.lease_until = None
            if action == "close":
                trial.closed_at = now
        await db.commit()
        return trial

    @staticmethod
    def gap_since(trial, now, cadence_ms):
        """Start of an open window gap (the last window's receipt time), or None."""
        last = trial.last_av_window_at
        if last is not None and now - last > timedelta(milliseconds=GAP_FACTOR * cadence_ms):
            return last
        return None

    @staticmethod
    async def record_gap(db, trial, since, now):
        """One WINDOW_GAP row per gap (id derived from the gap start); later sightings extend it."""
        gap_ms = min(int((now - since).total_seconds() * 1000), MAX_DURATION_MS)
        event_id = uuid.uuid5(trial.id, f"gap:{since.astimezone(timezone.utc).isoformat()}")
        row = (await db.execute(select(BrowserIncident).where(
            BrowserIncident.trial_id == trial.id, BrowserIncident.event_id == event_id,
        ))).scalar_one_or_none()
        if row is not None:
            row.duration_ms = max(row.duration_ms, gap_ms)
            return row
        trial.event_count += 1
        row = BrowserIncident(trial_id=trial.id, event_id=event_id, sequence=trial.event_count, kind="WINDOW_GAP",
                              observed_at=since, received_at=now, duration_ms=gap_ms)
        db.add(row)
        return row

    @staticmethod
    async def kind_counts(db, trial, kinds, now):
        """(rows received in the last minute, rows in the trial) restricted to the given kinds."""
        row = (await db.execute(select(
            func.count().filter(BrowserIncident.received_at > now - timedelta(minutes=1)), func.count(),
        ).where(BrowserIncident.trial_id == trial.id, BrowserIncident.kind.in_(kinds)))).one()
        return row[0], row[1]

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
        # Each origin is capped on its own rows so audiovisual incidents never starve browser events.
        for kinds, per_minute, per_trial in ((BROWSER_KINDS, BROWSER_EVENTS_PER_MINUTE, BROWSER_EVENTS_PER_TRIAL),
                                             (AV_KINDS, AV_ROWS_PER_MINUTE, AV_ROWS_PER_TRIAL)):
            incoming = sum(1 for event in fresh if event.kind in kinds)
            if not incoming:
                continue
            recent, total = await cls.kind_counts(db, trial, kinds, now)
            if recent + incoming > per_minute or total + incoming > per_trial:
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

    @staticmethod
    async def open_episode(db, trial, kind, payload):
        """The same-kind row this window continues (within one cadence), extended in place, else None."""
        cadence = timedelta(milliseconds=payload.duration_ms)
        row = (await db.execute(select(BrowserIncident).where(
            BrowserIncident.trial_id == trial.id, BrowserIncident.kind == kind,
            BrowserIncident.observed_at <= payload.observed_at + cadence,
        ).order_by(BrowserIncident.observed_at.desc()).limit(1))).scalar_one_or_none()
        if row is None or row.observed_at + timedelta(milliseconds=row.duration_ms) + cadence < payload.observed_at:
            return None
        window_end = payload.observed_at + cadence
        extended = int((window_end - row.observed_at).total_seconds() * 1000)
        row.duration_ms = min(MAX_DURATION_MS, max(row.duration_ms, extended))
        return row

    @classmethod
    async def process_av_window(cls, db, user, trial_id, payload: AVWindowRequest):
        # Phase 1: authorize under the row lock, then end the transaction so the lock is released.
        trial = await cls.owned(db, user, trial_id, lock=True)
        cls.leased(trial, payload.tab_id, utcnow())
        trial_key = str(trial.id)
        embedding = user.biometric_embedding
        gaze_zone = dict(trial.gaze_zone) if trial.gaze_zone else None
        await db.commit()

        # Phase 2: CPU-heavy inference on a bounded worker pool, off the event loop and without any lock.
        result = await asyncio.get_running_loop().run_in_executor(_AV_EXECUTOR, functools.partial(
            ContinuousSupervisionService.assess_window,
            frames_b64=payload.frames,
            audio_samples=payload.audio_samples,
            mode=payload.mode,
            biometric_embedding_json=embedding,
            trial_id=trial_key,
            duration_ms=payload.duration_ms,
            gaze_zone=gaze_zone,
            frame_times_ms=payload.frame_times_ms,
            gaze_samples=payload.gaze_samples,
            observed_at_ms=int(payload.observed_at.timestamp() * 1000),
        ))

        # Phase 3: the lease may have been lost meanwhile; re-lock, re-verify and only then persist.
        trial = await cls.owned(db, user, trial_id, lock=True)
        now = utcnow()
        cls.leased(trial, payload.tab_id, now)

        created_incidents = []
        anomalies = list(result["anomalies"])
        since = cls.gap_since(trial, now, payload.duration_ms)
        trial.last_av_window_at = now
        if since is not None:
            created_incidents.append(await cls.record_gap(db, trial, since, now))
            anomalies.append("WINDOW_GAP")

        slots = None
        for anomaly in result["anomalies"]:
            event_id = uuid.uuid5(payload.window_id, anomaly)
            existing = (await db.execute(select(BrowserIncident).where(
                BrowserIncident.trial_id == trial.id, BrowserIncident.event_id == event_id,
            ))).scalar_one_or_none()
            if existing is not None:
                created_incidents.append(existing)
                continue
            episode = await cls.open_episode(db, trial, anomaly, payload)
            if episode is not None:
                created_incidents.append(episode)
                continue
            if slots is None:
                recent, total = await cls.kind_counts(db, trial, AV_KINDS, now)
                slots = max(0, min(AV_ROWS_PER_MINUTE - recent, AV_ROWS_PER_TRIAL - total))
            if slots == 0:
                continue  # over the audiovisual cap: still reported to the caller, not stored
            slots -= 1
            trial.event_count += 1
            incident = BrowserIncident(
                trial_id=trial.id, event_id=event_id, sequence=trial.event_count, kind=anomaly,
                observed_at=payload.observed_at, received_at=now, duration_ms=payload.duration_ms,
            )
            db.add(incident)
            created_incidents.append(incident)

        await db.commit()

        return {
            "window_id": payload.window_id,
            "face_count": result["face_count"],
            "head_orientation": result["head_orientation"],
            "identity_match": result["identity_match"],
            "speech_detected": result["speech_detected"],
            "mouth_moving": result["mouth_moving"],
            "mouth_sync": result["mouth_sync"],
            "multiple_speakers": result["multiple_speakers"],
            "noise_level": result["noise_level"],
            "occlusion": result.get("occlusion", {"face": False, "mouth": False}),
            "camera_blocked": result.get("camera_blocked", False),
            "anomalies": anomalies,
            "incidents_created": [IncidentResponse.model_validate(inc) for inc in created_incidents],
        }

    @classmethod
    async def calibrate_gaze(cls, db, user, trial_id, payload: GazeCalibrationRequest):
        """Computes and stores the trial's screen zone from the five labelled calibration points."""
        # Phase 1: authorize under the row lock, then release it before the CPU-heavy measurement.
        trial = await cls.owned(db, user, trial_id, lock=True)
        cls.leased(trial, payload.tab_id, utcnow())
        await db.commit()

        frames = {point.target: point.frames for point in payload.points}
        try:
            batches = await asyncio.get_running_loop().run_in_executor(
                _AV_EXECUTOR, ContinuousSupervisionService.analyze_gaze_targets, frames)
            zone = compute_zone(batches)
        except GazeCalibrationError as error:
            status, message = GAZE_CALIBRATION_ERRORS[error.code]
            reject(status, message)

        # Phase 3: the lease may have been lost meanwhile; re-lock, re-verify and only then persist.
        trial = await cls.owned(db, user, trial_id, lock=True)
        cls.leased(trial, payload.tab_id, utcnow())
        trial.gaze_zone = zone.to_dict()
        await db.commit()
        return {"zone": trial.gaze_zone, "frames_used": sum(len(batch.frames) for batch in batches.values())}
