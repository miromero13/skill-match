from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "skillmatch",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.football.tasks", "app.tasks.session_reminders"],
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
    beat_schedule={
        "session-reminders-every-five-minutes": {
            "task": "sessions.dispatch_due_reminders",
            "schedule": 300.0,
        }
    },
)
