from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Coroutine
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar

from celery import Celery, Task

from app.core.config import settings
from app.football.config import load_football_config
from app.football.pipeline.audio_events import detect_audio_impact_events
from app.football.pipeline.ball_tracker import BallTrack, track_ball_in_video
from app.football.pipeline.challenge_engine import (
    ChallengeEvaluationSummary,
    evaluate_challenge_plan,
    generate_plan,
)
from app.football.pipeline.features import extract_session_features
from app.football.pipeline.fraud import evaluate_fraud_signals, inspect_video_integrity
from app.football.pipeline.fusion import (
    FusionSummary,
    fuse_audio_video_events,
)
from app.football.pipeline.scoring import score_session_features
from app.football.pipeline.touch_events import detect_video_touch_events

logger = logging.getLogger("skillmatch.football.tasks")

_T = TypeVar("_T")


def _run_coroutine_sync(coro: Coroutine[Any, Any, _T]) -> _T:
    """
    Run an async DB-bound coroutine from a sync Celery task. A real Celery worker
    has no running event loop, so `asyncio.run` works directly. `task_always_eager`
    (used in tests) executes the task inline inside the caller's own event loop,
    where `asyncio.run` would raise; in that case run it on a dedicated thread
    with its own loop instead.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, coro).result()


celery_app = Celery(
    "skillmatch_football",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
    task_eager_propagates=True,
    # In eager mode (dev/tests) also persist the outcome in the result backend so
    # `AsyncResult(task_id)` (the training status endpoint) can find it.
    task_store_eager_result=True,
)


@celery_app.task(name="football.process_session")
def process_session(
    session_id: str,
    video_path: str | None = None,
    audio_path: str | None = None,
    calibration_touch_ms: int | None = None,
    seed: int | None = None,
    segments_plan: list[dict[str, Any]] | None = None,
    client_events: list[dict[str, Any]] | None = None,
    expected_duration_s: float | None = None,
    detected_faces_count: int = 1,
) -> dict[str, Any]:
    """
    Celery pipeline entrypoint task for football skill validation.
    Executes the full pure pipeline in order:
    `ball_tracker -> touch_events -> audio_events -> fusion -> challenge_engine -> features -> scoring -> fraud`.
    """
    cfg = load_football_config()
    logger.info(
        "Processing football validation session_id=%s with config_version=%s",
        session_id,
        cfg.version,
    )

    video_touches: list[dict[str, Any]] = []
    audio_impacts: list[dict[str, Any]] = []
    fusion_payload: dict[str, Any] | None = None
    challenge_payload: dict[str, Any] | None = None
    features_payload: dict[str, Any] | None = None
    scoring_payload: dict[str, Any] | None = None
    fraud_payload: dict[str, Any] | None = None
    tracked_frames = 0

    track: BallTrack | None = None
    candidates = []
    video_integrity: dict[str, Any] | None = None
    actual_video_duration_s: float | None = None

    if video_path and Path(video_path).exists():
        track = track_ball_in_video(video_path)
        tracked_frames = len(track.points)
        if track.fps > 0 and tracked_frames > 0:
            actual_video_duration_s = tracked_frames / float(track.fps)
        candidates = detect_video_touch_events(track)
        video_integrity = inspect_video_integrity(video_path)
        video_touches = [
            {
                "t_ms": c.t_ms,
                "frame_idx": c.frame_idx,
                "height_diameters": round(c.height_diameters, 3),
                "confidence": round(c.confidence, 3),
            }
            for c in candidates
        ]

    audio_events = []
    if audio_path and Path(audio_path).exists():
        audio_events = detect_audio_impact_events(audio_path)
        audio_impacts = [
            {
                "t_ms": a.t_ms,
                "strength": a.strength,
                "confidence": a.confidence,
            }
            for a in audio_events
        ]

    fused_summary = FusionSummary()
    if candidates or audio_events:
        fused_summary = fuse_audio_video_events(
            video_events=candidates,
            audio_events=audio_events,
            calibration_touch_ms=calibration_touch_ms,
        )
        fusion_payload = {
            "confirmed_count": fused_summary.confirmed_count,
            "video_only_count": fused_summary.video_only_count,
            "audio_only_count": fused_summary.audio_only_count,
            "effective_touch_count": fused_summary.effective_touch_count,
            "coherence": fused_summary.coherence,
            "drift_ms_per_min": fused_summary.drift_ms_per_min,
            "estimated_calibration_offset_ms": fused_summary.estimated_calibration_offset_ms,
            "events": [
                {
                    "t_ms": ev.t_ms,
                    "estado": ev.estado,
                    "confianza": ev.confianza,
                }
                for ev in fused_summary.events
            ],
        }

    active_plan = segments_plan
    if active_plan is None and seed is not None:
        active_plan, _ = generate_plan(seed)

    challenge_eval: ChallengeEvaluationSummary | None = None
    if active_plan and fused_summary.events:
        challenge_eval = evaluate_challenge_plan(
            segments_plan=active_plan,
            fused_events=fused_summary.events,
            track=track,
        )
        challenge_payload = {
            "mean_compliance": challenge_eval.mean_compliance,
            "mean_reaction_latency_ms": challenge_eval.mean_reaction_latency_ms,
            "plan_coherent": challenge_eval.plan_coherent,
            "incoherent_segments_count": challenge_eval.incoherent_segments_count,
            "segments": [
                {
                    "indice": s.indice,
                    "tipo": s.tipo,
                    "inicio_servidor_ms": s.inicio_servidor_ms,
                    "duracion_ms": s.duracion_ms,
                    "cumplimiento": s.cumplimiento,
                    "latencia_reaccion_ms": s.latencia_reaccion_ms,
                    "median_height_diameters": s.median_height_diameters,
                    "median_interval_s": s.median_interval_s,
                    "touch_count": s.touch_count,
                }
                for s in challenge_eval.segments
            ],
        }

    if candidates or audio_events:
        features_payload = extract_session_features(
            track=track,
            fusion=fused_summary,
            challenge_eval=challenge_eval,
            session_duration_s=actual_video_duration_s or expected_duration_s,
        )
        scoring_out = score_session_features(features_payload)
        fraud_out = evaluate_fraud_signals(
            fusion=fused_summary,
            challenge_eval=challenge_eval,
            track=track,
            client_events=client_events,
            video_integrity=video_integrity,
            expected_duration_s=expected_duration_s,
            actual_video_duration_s=actual_video_duration_s,
            detected_faces_count=detected_faces_count,
        )

        final_needs_review = (
            scoring_out.requiere_revision or fraud_out.requiere_revision
        )
        scoring_payload = {
            "nivel": scoring_out.nivel,
            "probabilidades": scoring_out.probabilidades,
            "confianza": scoring_out.confianza,
            "requiere_revision": final_needs_review,
            "retroalimentacion": scoring_out.retroalimentacion,
            "version_modelo": scoring_out.version_modelo,
            "version_config": scoring_out.version_config,
        }
        fraud_payload = {
            "puntaje_riesgo": fraud_out.puntaje_riesgo,
            "requiere_revision": fraud_out.requiere_revision,
            "invalidada": fraud_out.invalidada,
            "incidencias": [
                {
                    "tipo": inc.tipo,
                    "severidad": inc.severidad,
                    "t_ms": inc.t_ms,
                    "detalle": inc.detalle,
                }
                for inc in fraud_out.incidencias
            ],
        }

    status_label = "processed_phase0_stub"
    if challenge_payload is not None:
        status_label = "processed_phase4"
    elif video_path and audio_path:
        status_label = "processed_phase3"
    elif video_path:
        status_label = "processed_phase2"

    return {
        "session_id": str(session_id),
        "status": status_label,
        "config_version": cfg.version,
        "config_hash": cfg.config_hash,
        "tracked_frames": tracked_frames,
        "video_touch_count": len(video_touches),
        "video_touches": video_touches,
        "audio_impact_count": len(audio_impacts),
        "fusion": fusion_payload,
        "challenges": challenge_payload,
        "features": features_payload,
        "scoring": scoring_payload,
        "fraud": fraud_payload,
        "processed_at": datetime.now(UTC).isoformat(),
    }


@celery_app.task(name="football.train_level_model", bind=True)
def train_level_model_task(
    self: Task,
    version_tag: str | None = None,
    activate: bool = True,
    dataset_source: str = "all",
    sample_ids: list[str] | None = None,
    skill_id: str | None = None,
) -> dict[str, Any]:
    """
    Celery entrypoint for training the football level classifier. Opens its own
    async DB engine/session (training is not request-scoped once queued) and reports
    `processed`/`total`/`message` via `self.update_state` as each dataset_sample
    is processed, so the Training Studio can poll real progress instead of
    blocking on a single HTTP call.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.football.services.training_service import train_football_level_model

    # `self.request` is thread-local; the coroutine may run on a helper thread
    # (see `_run_coroutine_sync`), so capture the id here instead of reading it there.
    task_id = self.request.id

    def on_progress(processed: int, total: int, message: str) -> None:
        self.update_state(
            task_id=task_id,
            state="PROGRESS",
            meta={"processed": processed, "total": total, "message": message},
        )

    async def _run() -> dict[str, Any]:
        # Each task run executes in its own event loop (`asyncio.run`), so it can't
        # reuse the app-wide pooled engine whose connections are bound to another
        # loop. A throwaway NullPool engine keeps connections loop-local.
        engine = create_async_engine(settings.async_database_url, poolclass=NullPool)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as db:
                return await train_football_level_model(
                    db=db,
                    version_tag=version_tag,
                    activate=activate,
                    dataset_source=dataset_source,
                    sample_ids=[uuid.UUID(s) for s in sample_ids] if sample_ids else None,
                    skill_id=uuid.UUID(skill_id) if skill_id else None,
                    on_progress=on_progress,
                )
        finally:
            await engine.dispose()

    return _run_coroutine_sync(_run())
