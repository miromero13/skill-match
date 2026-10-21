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

## 2. Gestión de Variables de Entorno y Secretos (.env)

El backend utiliza **Pydantic Settings** con tipado fuerte. Todas las variables y credenciales deben provenir estrictamente de tu archivo `.env` o del entorno.

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

# --- Credenciales del Administrador Inicial (Seed Automático) ---
ADMIN_EMAIL="admin@skillmatch.io"
ADMIN_PASSWORD="SuperSecretAdminPassword123!"
ADMIN_FULL_NAME="Administrador Principal"

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

---

## 3. Puesta en Marcha Multiplataforma

### 🍎 Opción 1: En macOS (MacBook - Guía Principal)

Requisitos: Python 3.12 o 3.13 (instalado nativamente o vía Homebrew: `brew install python@3.13`).

1. **Crear y activar el entorno virtual estándar con `python3`:**
   ```bash
   cd backend
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. **Instalar dependencias con `pip`:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. **Configurar el archivo `.env`:**
   Copia la plantilla `env.template` al archivo `.env`:
   ```bash
   cp env.template .env
   ```

4. **Ejecutar migraciones en la base de datos:**
   ```bash
   alembic upgrade head
   ```

5. **Iniciar el servidor de desarrollo:**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

---

### 🐧 Opción 2: En Linux (Ubuntu / Debian / Fedora)

1. **Instalar dependencias del sistema y crear entorno:**
   ```bash
   sudo apt update && sudo apt install -y python3-venv python3-pip
   cd backend
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. **Instalar requerimientos y migrar:**
   ```bash
   pip install -r requirements.txt
   cp env.template .env
   alembic upgrade head
   ```

3. **Iniciar servidor:**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

---

### 🪟 Opción 3: En Windows (PowerShell / Command Prompt)

1. **Crear y activar entorno virtual:**
   ```powershell
   cd backend
   python -m venv .venv
   .venv\Scripts\activate
   ```

2. **Instalar dependencias:**
   ```powershell
   pip install -r requirements.txt
   copy env.template .env
   ```

3. **Ejecutar migraciones y arrancar:**
   ```powershell
   alembic upgrade head
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

---

## 4. ¿Cómo Probar la Base de Datos con TablePlus?

1. Abre **TablePlus** en tu MacBook.
2. Haz clic en **Create a new connection...** $\to$ Selecciona **PostgreSQL**.
3. Ingresa los datos configurados en tu `.env`:
   - **Name:** `SkillMatch Local`
   - **Host:** `localhost` o `127.0.0.1`
   - **Port:** `5432`
   - **User:** `skillmatch_user`
   - **Password:** `skillmatch_password`
   - **Database:** `skillmatch_db`
4. Haz clic en **Test** (debe marcarse todo en verde) y luego en **Connect**.
5. Verás la tabla `alembic_version` que confirma que las migraciones están activas y sincronizadas.

---

## 5. ¿Cómo Probar la API y Swagger UI?

Una vez levantado el servidor (`uvicorn app.main:app --reload`):

1. **Documentación Interactiva (Swagger UI):**
   Abre en tu navegador:
   👉 **`http://localhost:8000/docs`**
   Allí podrás ver y probar interactivamente todos los endpoints con sus contratos y respuestas en vivo.

2. **Endpoint de Salud del Sistema:**
   Abre en tu navegador o terminal:
   👉 **`http://localhost:8000/api/health`**
   
   Respuesta esperada (JSON canónico):
   ```json
   {
     "statuscode": 200,
     "message": "Sistema operativo y base de datos conectada exitosamente",
     "data": {
       "status": "healthy",
       "environment": "development",
       "version": "0.1.0",
       "database": "connected",
       "services": {
         "api": "operational",
         "database_engine": "asyncpg_sqlalchemy2"
       }
     },
     "count": null
   }
   ```

---

## 6. Ejecución de Pruebas Automatizadas (Pytest)

Para verificar en cualquier momento que todos los contratos, excepciones y middlewares funcionan al 100%:
```bash
pytest -v
```
*(5 tests automatizados cubriendo respuesta unificada 200, 404, validaciones 422, cabeceras preventivas y salud).*
