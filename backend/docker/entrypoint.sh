#!/bin/sh
# SkillMatch backend container entrypoint.
# Roles: api (default) | worker | beat | migrate | any other command (exec as-is).
# Extra arguments after a role are appended to that role's command.
set -eu

role="${1:-api}"
if [ "$#" -gt 0 ]; then
    shift
fi

case "$role" in
    api)
        if [ "${UVICORN_RELOAD:-false}" = "true" ]; then
            exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers \
                --forwarded-allow-ips='*' --reload --reload-dir /app/app "$@"
        fi
        exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers \
            --forwarded-allow-ips='*' --workers "${UVICORN_WORKERS:-1}" "$@"
        ;;
    worker)
        exec celery -A app.core.celery_app.celery_app worker \
            --loglevel "${CELERY_LOG_LEVEL:-info}" --concurrency "${CELERY_CONCURRENCY:-2}" "$@"
        ;;
    beat)
        exec celery -A app.core.celery_app.celery_app beat \
            --loglevel "${CELERY_LOG_LEVEL:-info}" --schedule /tmp/celerybeat-schedule "$@"
        ;;
    migrate)
        # "heads" (plural): the history currently has several unmerged heads, and
        # `upgrade head` aborts with "Multiple head revisions are present".
        # It is equivalent to `upgrade head` once the history has a single head.
        exec alembic upgrade heads "$@"
        ;;
    *)
        exec "$role" "$@"
        ;;
esac
