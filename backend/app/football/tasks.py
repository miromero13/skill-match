from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from celery import Celery

from app.core.config import settings
from app.football.config import load_football_config
from app.football.pipeline.audio_events import detect_audio_impact_events
from app.football.pipeline.ball_tracker import BallTrack, track_ball_in_video
from app.football.pipeline.challenge_engine import (
    evaluate_challenge_plan,
    generate_plan,
)
from app.football.pipeline.fusion import FusedTouchEvent, fuse_audio_video_events
from app.football.pipeline.touch_events import detect_video_touch_events

logger = logging.getLogger("skillmatch.football.tasks")

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
)


@celery_app.task(name="football.process_session")
def process_session(
    session_id: str,
    video_path: str | None = None,
    audio_path: str | None = None,
    calibration_touch_ms: int | None = None,
    seed: int | None = None,
    segments_plan: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Celery pipeline entrypoint task for football skill validation.
    Executes `ball_tracker`, `touch_events`, `audio_events`, `fusion`, and
    `challenge_engine` when media/plan inputs are provided.
    Subsequent phases plug in `features`, `scoring`, and `fraud`.
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
    tracked_frames = 0

    track: BallTrack | None = None
    candidates = []
    if video_path and Path(video_path).exists():
        track = track_ball_in_video(video_path)
        tracked_frames = len(track.points)
        candidates = detect_video_touch_events(track)
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

    fused_events: list[FusedTouchEvent] = []
    if candidates or audio_events:
        fused = fuse_audio_video_events(
            video_events=candidates,
            audio_events=audio_events,
            calibration_touch_ms=calibration_touch_ms,
        )
        fused_events = fused.events
        fusion_payload = {
            "confirmed_count": fused.confirmed_count,
            "video_only_count": fused.video_only_count,
            "audio_only_count": fused.audio_only_count,
            "effective_touch_count": fused.effective_touch_count,
            "coherence": fused.coherence,
            "drift_ms_per_min": fused.drift_ms_per_min,
            "estimated_calibration_offset_ms": fused.estimated_calibration_offset_ms,
            "events": [
                {
                    "t_ms": ev.t_ms,
                    "estado": ev.estado,
                    "confianza": ev.confianza,
                }
                for ev in fused.events
            ],
        }

    active_plan = segments_plan
    if active_plan is None and seed is not None:
        active_plan, _ = generate_plan(seed)

    if active_plan and fused_events:
        challenge_eval = evaluate_challenge_plan(
            segments_plan=active_plan,
            fused_events=fused_events,
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
        "processed_at": datetime.now(UTC).isoformat(),
    }
