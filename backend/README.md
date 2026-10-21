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

### Tabla Canónica de Variables de Entorno

| Variable | Tipo / Secreto | Requerido | Valor por Defecto (Dev) | Propósito y Descripción |
|---|:---:|:---:|---|---|
| `PROJECT_NAME` | `str` | No | `"SkillMatch API"` | Nombre de la aplicación en OpenAPI / Swagger. |
| `VERSION` | `str` | No | `"0.1.0"` | Versión del backend. |
| `ENVIRONMENT` | `str` | Sí | `"development"` | Entorno (`development`, `staging`, `production`). En prod valida secretos obligatorios. |
| `DEBUG` | `bool` | No | `True` | Activa logs verbosos y debug. |
| `ALLOWED_ORIGINS` | `list[str]` | No | `http://localhost:3000,...` | Dominios autorizados para políticas de CORS. |
| **`POSTGRES_HOST`** | `str` | Sí | `"localhost"` | Host del servidor PostgreSQL. |
| **`POSTGRES_PORT`** | `int` | Sí | `5432` | Puerto de PostgreSQL. |
| **`POSTGRES_USER`** | `str` | Sí | `"skillmatch_user"` | Usuario de la base de datos. |
| **`POSTGRES_PASSWORD`** | **`SecretStr` (Secreto)** | **Sí** | `"skillmatch_password"` | Contraseña de PostgreSQL. En producción se exige una clave segura. |
| **`POSTGRES_DB`** | `str` | Sí | `"skillmatch_db"` | Nombre de la base de datos. |
| **`DATABASE_URL`** | **`SecretStr` (Secreto)** | No | `None` | DSN directa opcional (`postgresql+asyncpg://...`). |
| `DB_POOL_SIZE` | `int` | No | `10` | Tamaño base del pool de conexiones `asyncpg`. |
| `DB_MAX_OVERFLOW` | `int` | No | `20` | Conexiones adicionales permitidas bajo carga. |
| **`SECRET_KEY`** | **`SecretStr` (Secreto)** | **Sí** | Clave dev por defecto | Clave criptográfica para firma de JWT (generar con `openssl rand -hex 32`). |
| `ALGORITHM` | `str` | No | `"HS256"` | Algoritmo de firma de tokens JWT. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `int` | No | `1440` (24h) | Tiempo de expiración del Access Token. |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `int` | No | `30` | Tiempo de expiración del Refresh Token. |
| `GOOGLE_CLIENT_ID` | `str` | En Sprint 0 (HU-07) | `None` | Client ID de Google OAuth 2.0. |
| **`GOOGLE_CLIENT_SECRET`** | **`SecretStr` (Secreto)** | En Sprint 0 (HU-07) | `None` | Secreto de Google OAuth 2.0. |
| `GITHUB_CLIENT_ID` | `str` | En Sprint 0 (HU-07) | `None` | Client ID de GitHub OAuth. |
| **`GITHUB_CLIENT_SECRET`** | **`SecretStr` (Secreto)** | En Sprint 0 (HU-07) | `None` | Secreto de GitHub OAuth. |
| **`WHATSAPP_API_KEY`** | **`SecretStr` (Secreto)** | En Sprint 0 (HU-07) | `None` | API Key de WhatsApp Cloud para OTP. |
| `WHATSAPP_PHONE_NUMBER_ID`| `str` | En Sprint 0 (HU-07) | `None` | ID del número telefónico de WhatsApp Business. |
| `MINIO_ENDPOINT` | `str` | No | `"localhost:9000"` | Endpoint del almacenamiento S3 / MinIO. |
| `MINIO_ROOT_USER` | `str` | No | `"minioadmin"` | Usuario root de MinIO. |
| **`MINIO_ROOT_PASSWORD`** | **`SecretStr` (Secreto)** | **Sí** | `"minioadmin"` | Contraseña administrativa de MinIO. |
| `MINIO_DEFAULT_BUCKET` | `str` | No | `"skillmatch-media"` | Bucket para audios, videos y evidencias. |

> **Regla de Producción:** El backend incluye un validador en `Settings` (`validate_production_secrets`) que **bloquea el inicio de la aplicación** en entornos `production` o `staging` si se detecta que `SECRET_KEY` o `POSTGRES_PASSWORD` conservan valores por defecto de desarrollo.

---

## 3. Puesta en Marcha

### Opción A: Ejecución con Docker Compose (Recomendado)
Para levantar la base de datos PostgreSQL persistente y la API FastAPI contenedorizada:
```bash
# Desde la raíz del repositorio:
docker compose up -d --build

# Ver logs de la API:
docker compose logs -f api
```
- La API estará accesible en: `http://localhost:8000`
- Documentación Swagger UI: `http://localhost:8000/docs`
- Verificación de salud: `http://localhost:8000/api/health`

---

### Opción B: Ejecución Local en Entorno Virtual

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

3. **Levantar PostgreSQL con Docker:**
   ```bash
   # En la raíz del proyecto:
   docker compose up -d postgres
   ```

4. **Ejecutar migraciones de base de datos con Alembic:**
   ```bash
   cd backend
   alembic upgrade head
   ```

5. **Iniciar el servidor de desarrollo:**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

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
