# syntax=docker/dockerfile:1.7
# ==============================================================================
# SkillMatch backend image (API, Celery worker/beat, migrations).
# Build context: ./backend. Roles are selected through docker-entrypoint
# (api | worker | beat | migrate | <any command>). Health checks are defined
# per role in compose, never here.
# ==============================================================================

ARG PYTHON_IMAGE=python:3.12-slim-bookworm

# ------------------------------------------------------------------------------
# uv binary (pinned)
# ------------------------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:0.13.7 AS uv

# ------------------------------------------------------------------------------
# Docker CLI (static binary) used by the programming sandbox runner against dind
# ------------------------------------------------------------------------------
FROM docker:28-cli AS docker-cli

# ------------------------------------------------------------------------------
# Stage 1: Python dependencies from uv.lock into /opt/venv
# ------------------------------------------------------------------------------
FROM ${PYTHON_IMAGE} AS deps

COPY --from=uv /uv /uvx /bin/

ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=/usr/local/bin/python3.12

WORKDIR /build

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev --no-install-project

# ------------------------------------------------------------------------------
# Stage 2: pinned ML models downloaded and SHA-256 verified at build time.
# The installers derive their destination from __file__ (<root>/app/models/weights),
# so scripts/ is laid out next to app/ under /build.
# ------------------------------------------------------------------------------
FROM ${PYTHON_IMAGE} AS models

WORKDIR /build

COPY scripts/install_vision_models.py scripts/install_calibration_audio_models.py ./scripts/

RUN python scripts/install_vision_models.py \
    && python scripts/install_calibration_audio_models.py

# ------------------------------------------------------------------------------
# Stage 3: runtime
# ------------------------------------------------------------------------------
FROM ${PYTHON_IMAGE} AS runtime

LABEL org.opencontainers.image.title="skillmatch-backend" \
      org.opencontainers.image.description="SkillMatch backend: FastAPI API, Celery worker/beat and Alembic migrations" \
      org.opencontainers.image.source="https://github.com/miromero13/skill-match"

# Runtime system libraries: OpenCV/MediaPipe (libglib2.0-0, libgl1; libegl1 + libgles2 are
# dlopen'ed by MediaPipe's FaceLandmarker even on CPU, otherwise face_landmarker fails to load
# with "libEGL.so.1: cannot open shared object file"), audio/video decoding (ffmpeg), TLS roots.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libgl1 \
        libegl1 \
        libgles2 \
        ffmpeg \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system --gid 10001 skillmatch \
    && useradd --system --uid 10001 --gid 10001 --home-dir /app --no-create-home \
        --shell /usr/sbin/nologin skillmatch

COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=deps /opt/venv /opt/venv

# HOME (/app) is not writable by the runtime user: point tool caches (fontconfig via
# matplotlib/OpenCV, matplotlib config) at /tmp so they don't log "No writable cache directories".
ENV VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    XDG_CACHE_HOME=/tmp/.cache \
    MPLCONFIGDIR=/tmp/.config/matplotlib

WORKDIR /app

COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
COPY app ./app
# Top-level `ml/` package (repo root) imported by app.football.services.training_service
# (`from ml.export...`, `from ml.train...`). It lives outside this build context, so it
# arrives as the named build context `ml` (compose: build.additional_contexts;
# plain docker: `docker build --build-context ml=../ml backend`). /app is the working
# directory, which uvicorn/celery put on sys.path, so `import ml` resolves.
COPY --from=ml . ./ml
COPY scripts/install_vision_models.py scripts/install_calibration_audio_models.py ./scripts/
COPY --from=models /build/app/models/weights ./app/models/weights

# Re-check the baked models against their pinned SHA-256 (no network, no writes).
RUN python scripts/install_vision_models.py --verify-only \
    && python scripts/install_calibration_audio_models.py --verify-only

RUN mkdir -p /app/storage /sandbox-work \
    && chown 10001:10001 /app/storage /sandbox-work

COPY --chmod=0755 docker/entrypoint.sh /usr/local/bin/docker-entrypoint

USER 10001:10001

EXPOSE 8000

ENTRYPOINT ["docker-entrypoint"]
CMD ["api"]
