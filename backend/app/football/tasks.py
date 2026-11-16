from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from celery import Celery

from app.core.config import settings
from app.football.config import load_football_config
from app.football.pipeline.ball_tracker import track_ball_in_video
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
) -> dict[str, Any]:
    """
    Celery pipeline entrypoint task for football skill validation.
    Executes `ball_tracker` and `touch_events` when `video_path` is provided.
    Subsequent phases plug in `audio_events`, `fusion`, `challenge_engine`,
    `features`, `scoring`, and `fraud`.
    """
    cfg = load_football_config()
    logger.info(
        "Processing football validation session_id=%s with config_version=%s",
        session_id,
        cfg.version,
    )

    video_touches: list[dict[str, Any]] = []
    tracked_frames = 0

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

    return {
        "session_id": str(session_id),
        "status": "processed_phase0_stub" if not video_path else "processed_phase2",
        "config_version": cfg.version,
        "config_hash": cfg.config_hash,
        "tracked_frames": tracked_frames,
        "video_touch_count": len(video_touches),
        "video_touches": video_touches,
        "processed_at": datetime.now(UTC).isoformat(),
    }
