from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from celery import Celery

from app.core.config import settings
from app.football.config import load_football_config

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
def process_session(session_id: str) -> dict[str, Any]:
    """
    Phase 0 Celery pipeline entrypoint task for football skill validation.
    Subsequent phases plug in `ball_tracker`, `touch_events`, `audio_events`,
    `fusion`, `challenge_engine`, `features`, `scoring`, and `fraud`.
    """
    cfg = load_football_config()
    logger.info(
        "Processing football validation session_id=%s with config_version=%s",
        session_id,
        cfg.version,
    )
    return {
        "session_id": str(session_id),
        "status": "processed_phase0_stub",
        "config_version": cfg.version,
        "config_hash": cfg.config_hash,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }
