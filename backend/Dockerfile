# ==========================================
# Multi-stage Dockerfile para SkillMatch API
# ==========================================

# Etapa 1: Builder
FROM python:3.13-slim AS builder

WORKDIR /build

# Instalar dependencias del sistema necesarias para compilar paquetes si aplica
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar uv para resolución ultrarrápida y determinística
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copiar archivos de dependencias
COPY pyproject.toml README.md ./

# Crear entorno virtual y sincronizar dependencias de producción
RUN uv venv /opt/venv --python /usr/local/bin/python3 && \
    uv pip install --no-cache --python /opt/venv/bin/python "."

# ==========================================
# Etapa 2: Runtime Final
# ==========================================
FROM python:3.13-slim AS runner

WORKDIR /app

# Crear usuario no privilegiado para mayor seguridad
RUN groupadd -g 10001 skillmatch && \
    useradd -u 10001 -g skillmatch -s /bin/bash -m skillmatch

# Instalar utilitarios mínimos de runtime (curl para healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar el entorno virtual preparado
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Copiar código de aplicación y configuración de migraciones
COPY app /app/app
COPY alembic /app/alembic
COPY alembic.ini /app/alembic.ini
COPY env.template /app/env.template

RUN chown -R skillmatch:skillmatch /app

USER skillmatch

EXPOSE 8000

# Healthcheck interno del contenedor
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Comando de inicio del servidor ASGI
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
