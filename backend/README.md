# SkillMatch — Backend API

Backend asíncrono para la plataforma de intercambio colaborativo de habilidades **SkillMatch**, construido con **FastAPI**, **SQLAlchemy 2.0 (asyncpg)**, **PostgreSQL** y **Alembic**.

---

## 1. Arquitectura y Tecnologías
- **Framework:** FastAPI con arquitectura modular orientada al dominio.
- **ORM & Persistencia:** SQLAlchemy 2.0 con driver asíncrono `asyncpg`.
- **Migraciones:** Alembic configurado para ejecución asíncrona.
- **Contrato de Respuesta:** Sobre unificado y estándar `APIResponse[T]` (`statuscode`, `message`, `data`, `count`).
- **Seguridad:** Middlewares de CORS, compresión GZip, cabeceras preventivas y tokens JWT con claim dinámico de rol (`MEMBER` o `ADMIN`).
- **Documentación Viva:** Swagger UI interactivo en `/docs` y ReDoc en `/redoc`.

---

## 2. Gestión de Variables de Entorno y Secretos

El backend utiliza **Pydantic Settings** con tipado fuerte. Todos los secretos e información sensible están declarados explícitamente con `SecretStr` para **prevenir cualquier filtración accidental en logs, excepciones o serializaciones**.

Copia y pega la siguiente plantilla en tu archivo local `.env` (en `backend/.env` o en la raíz del proyecto):

```bash
# ==============================================================================
# SkillMatch Backend — Variables de Entorno (.env)
# ==============================================================================

# --- Configuración General de Entorno ---
PROJECT_NAME="SkillMatch API"
VERSION="0.1.0"
ENVIRONMENT="development"
DEBUG=True

# Orígenes autorizados para CORS (separados por coma)
ALLOWED_ORIGINS="http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173"

# --- Base de Datos PostgreSQL Asíncrona (asyncpg) ---
POSTGRES_HOST="localhost"
POSTGRES_PORT=5432
POSTGRES_USER="skillmatch_user"
POSTGRES_PASSWORD="skillmatch_password"
POSTGRES_DB="skillmatch_db"

# Opcional: DSN directa (anula host/port/user/password si se especifica)
# DATABASE_URL="postgresql+asyncpg://skillmatch_user:skillmatch_password@localhost:5432/skillmatch_db"

# Parámetros del Pool de Conexiones
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_POOL_TIMEOUT=30

# --- Seguridad Criptográfica y JWT ---
SECRET_KEY="09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=1440
REFRESH_TOKEN_EXPIRE_DAYS=30

# --- Proveedores de Autenticación Social & OTP (Sprint 0 - HU-07) ---
GOOGLE_CLIENT_ID=""
GOOGLE_CLIENT_SECRET=""

GITHUB_CLIENT_ID=""
GITHUB_CLIENT_SECRET=""

WHATSAPP_API_KEY=""
WHATSAPP_PHONE_NUMBER_ID=""

# --- Almacenamiento de Evidencias y MinIO S3 (Sprint 1 al 4) ---
MINIO_ENDPOINT="localhost:9000"
MINIO_ROOT_USER="minioadmin"
MINIO_ROOT_PASSWORD="minioadmin"
MINIO_SECURE=False
MINIO_DEFAULT_BUCKET="skillmatch-media"
```

> **Regla de Producción:** El backend incluye un validador en `Settings` (`validate_production_secrets`) que **bloquea el inicio de la aplicación** en entornos `production` o `staging` si se detecta que `SECRET_KEY` o `POSTGRES_PASSWORD` conservan valores por defecto de desarrollo.

---

## 3. Puesta en Marcha

### Ejecución Local en Entorno Virtual

1. **Configurar el entorno virtual con `uv`:**
   ```bash
   cd backend
   uv venv .venv --python python3.13
   source .venv/bin/activate
   uv pip install -e ".[dev]"
   ```

2. **Configurar variables de entorno:**
   Copia la plantilla `env.template` a tu archivo local `.env`:
   ```bash
   cp env.template .env
   ```

3. **Asegurar instancia de PostgreSQL:**
   Asegúrate de tener un servidor PostgreSQL activo con las credenciales indicadas en tu `.env`.

4. **Ejecutar migraciones de base de datos con Alembic:**
   ```bash
   cd backend
   alembic upgrade head
   ```

5. **Iniciar el servidor de desarrollo:**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
- La API estará accesible en: `http://localhost:8000`
- Documentación Swagger UI: `http://localhost:8000/docs`
- Verificación de salud: `http://localhost:8000/api/health`

---

## 4. Ejecución de Pruebas Automatizadas (Pytest)
Para correr la suite de pruebas unitarias y de integración:
```bash
cd backend
uv run pytest -v
```

---

## 5. Esquema del Sobre de Respuesta (APIResponse)
Todas las rutas responden estrictamente bajo este formato JSON:
```json
{
  "statuscode": 200,
  "message": "Operación completada exitosamente",
  "data": {
    "status": "healthy",
    "environment": "development",
    "version": "0.1.0",
    "database": "connected"
  },
  "count": null
}
```
En caso de error (400, 404, 422, 500), el middleware captura la excepción y la traduce automáticamente al sobre estándar con su respectivo `statuscode` y `message` descriptivo.
