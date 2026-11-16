from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from celery import Celery

from app.core.config import settings
from app.football.config import load_football_config
from app.football.pipeline.audio_events import detect_audio_impact_events
from app.football.pipeline.ball_tracker import track_ball_in_video
from app.football.pipeline.fusion import fuse_audio_video_events
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
) -> dict[str, Any]:
    """
    Celery pipeline entrypoint task for football skill validation.
    Executes `ball_tracker`, `touch_events`, `audio_events`, and `fusion`
    when `video_path` / `audio_path` are provided.
    Subsequent phases plug in `challenge_engine`, `features`, `scoring`, and `fraud`.
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
    tracked_frames = 0

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

    if candidates or audio_events:
        fused = fuse_audio_video_events(
            video_events=candidates,
            audio_events=audio_events,
            calibration_touch_ms=calibration_touch_ms,
        )
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

    status_label = "processed_phase0_stub"
    if video_path and audio_path:
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
        "processed_at": datetime.now(UTC).isoformat(),
    }
