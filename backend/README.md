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
- **Prueba de navegador (SM-43):** sesiones de ensayo e incidentes reales en `/api/browser-supervision/trials`, separados del examen y de los cupos. Requiere la migración aditiva `bc43a710d962` con autorización explícita, no se aplica al arrancar. Vista MEMBER `/app/browser-supervision-test`; guía, límites y pruebas: [`docs/browser-supervision.md`](../docs/browser-supervision.md). No incluye cámara/audio continuo ni sanciones.
- **Integridad audiovisual local (SM-44) y calibración sobre el motor de integridad:** `webrtcvad-wheels==2.0.14` y `sherpa-onnx==2.0.1`, sin API de audio en la nube. La calibración previa al examen (`POST /api/evaluations/{id}/liveness/verify-identity`) usa los mismos analizadores y umbrales que la supervisión (`app/services/integrity/`): movimiento con pose 3D, centro y cuatro esquinas de mirada, silencio, frase de control con video y lecturas de boca del navegador; guarda zona de mirada, huella de voz y referencia de oclusión (columnas JSON, migración `f3a8d2c19e47`) que nunca se devuelven. La evidencia nueva es obligatoria y sin el modelo de embeddings de hablante no hay calibración lista (503). Instalar dependencias y ejecutar desde `backend`: `.venv/bin/python scripts/install_calibration_audio_models.py`; verificar sin red con `--verify-only`. Modelos/hashes/licencias: [`docs/models/audio-integrity/README.md`](../docs/models/audio-integrity/README.md); contrato, comprobaciones y límites: [`docs/evaluation-calibration.md`](../docs/evaluation-calibration.md). `POST /api/browser-supervision/trials/{id}/voice-calibration` exige además `frames` muestreados para verificar la telemetría de boca. No hay descargas durante solicitudes ni aprobación degradada sin detector/modelos. Prototipo pendiente de prueba física/revisión independiente, no garantía anticopia.
- **Modelos faciales locales (S13 / T2):** YuNet, SFace (OpenCV Zoo, Apache-2.0) y MediaPipe `face_landmarker.task` (Apache-2.0) no se versionan (`*.onnx`, `weights/` ignorados). Descargar una vez con SHA-256 fijado, desde `backend`: `.venv/bin/python scripts/install_vision_models.py` (escritura atómica; rechaza cualquier archivo cuyo hash no coincida y nunca sobrescribe uno existente); verificar sin red con `--verify-only`. Se instalan en `app/models/weights/`. Al arrancar, la API registra un `ERROR` por cada modelo ausente o no cargable y sigue sirviendo el resto. Sin modelos el sistema **falla en cerrado**: el enrolamiento y la verificación de identidad responden `400` (imagen no decodificable) o `503` ("Servicio biométrico no disponible…", sin persistir nada ni rechazar al miembro), y las ventanas de supervisión registran el incidente `MODEL_UNAVAILABLE` con `face_count` 0 e identidad sin veredicto, nunca un rostro limpio ni un embedding sintético. MediaPipe se reintenta cada 30 s tras un fallo. Requiere `mediapipe>=1.2.3,<1.3` (en `requirements.txt` y `pyproject.toml`). Pruebas: `tests/test_vision_models_fail_closed.py`.

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
ALLOWED_ORIGINS="http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173,https://localhost,http://localhost,capacitor://localhost,http://192.168.1.8:5173,http://192.168.1.8:8000"

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
WS_TICKET_EXPIRE_SECONDS=30

# --- Credenciales del Administrador Inicial (Seed Automático) ---
ADMIN_EMAIL="admin@skillmatch.io"
ADMIN_PASSWORD="SuperSecretAdminPassword123!"
ADMIN_FULL_NAME="Administrador Principal"

# --- Autenticación de miembros exclusivamente con Google (Sprint 0 - HU-07) ---
# Google OAuth 2.0 (Google Identity Services / Web Client)
# Obtener en Google Cloud Console -> APIs & Services -> Credentials -> OAuth 2.0 Client IDs
GOOGLE_CLIENT_ID="tu-google-client-id.apps.googleusercontent.com"

# --- Corrección teórica opcional (texto; consentimiento explícito requerido) ---
THEORY_GRADING_PROVIDER="disabled" # disabled | openai | gemini
THEORY_GRADING_MODEL=""            # Identificador explícito, sin modelo por defecto
OPENAI_API_KEY=""                  # [SECRETO] Si provider=openai
GEMINI_API_KEY=""                  # [SECRETO] Si provider=gemini o para Asistente Virtual
ASSISTANT_GEMINI_MODEL="gemini-3.1-flash-lite" # Modelo del Asistente Virtual (gemini-3.1-flash-lite, gemini-flash-latest)
THEORY_GRADING_TIMEOUT_SECONDS=20
THEORY_ASR_ENABLED=True # Enable the installed local Whisper runtime for theory exams
# BROWSER_SUPERVISION_TRIAL_ENABLED=true  # Sin definir = activo solo en development/test, nunca en production (production lo fuerza apagado aunque sea true)
# INTEGRITY_DIAGNOSTICS_ENABLED=false  # Registro numérico por ventana AV para afinar umbrales (nunca imágenes, audio ni huellas); production lo fuerza apagado
# INTEGRITY_DIAGNOSTICS_DIR="/tmp/skillmatch-integrity-diagnostics"  # Carpeta de los <trial_id>.jsonl; por defecto bajo el directorio temporal del SO

# --- Sandbox seguro de programación (la imagen debe estar pre-descargada) ---
SANDBOX_DOCKER_IMAGE="python:3.12-slim"
SANDBOX_DOCKER_BINARY="docker"
SANDBOX_MAX_CONCURRENT_RUNS=2



# --- Almacenamiento de Evidencias y MinIO / Garage S3 (Coolify VPS) ---
MINIO_ENDPOINT="localhost:9000"
MINIO_ROOT_USER="minioadmin"
MINIO_ROOT_PASSWORD="minioadmin"
MINIO_SECURE=False
MINIO_DEFAULT_BUCKET="skillmatch-media"

GARAGE_S3_ENDPOINT_URL="https://s3.devhooh.com"
GARAGE_S3_ADMIN_URL="https://garage-admin.devhooh.com"
GARAGE_S3_WEB_URL="https://garage-web.devhooh.com"
GARAGE_S3_REGION="garage"
GARAGE_S3_ACCESS_KEY_ID="GK000000000000000000000000"
GARAGE_S3_SECRET_ACCESS_KEY="0000000000000000000000000000000000000000000000000000000000000000"
GARAGE_S3_ADMIN_TOKEN=""
GARAGE_S3_BUCKET="skillmatch-football"
GARAGE_S3_FORCE_PATH_STYLE=True

# --- Cola de Procesamiento Asíncrono (Celery + Redis) ---
REDIS_URL="redis://localhost:6379/0"
CELERY_TASK_ALWAYS_EAGER=False

# --- Economía de Puntos y Pasarela de Pagos (HU-42 / RF-SES-09 / RF-WAL-02) ---
PAYMENT_GATEWAY_PROVIDER="sandbox"
STRIPE_SECRET_KEY=""
STRIPE_PUBLISHABLE_KEY=""
PAYPAL_CLIENT_ID=""
PAYPAL_CLIENT_SECRET=""
WALLET_POINTS_PER_USD=10
WALLET_CASHOUT_MIN_POINTS=100
WALLET_PLATFORM_FEE_PERCENTAGE=15.0

# --- Notificaciones Push Nativas (Firebase Cloud Messaging - FCM) ---
FIREBASE_CREDENTIALS_PATH="firebase-credentials.json"
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

Usá una **base PostgreSQL nueva y descartable**, nunca la base con datos de la aplicación. Primero confirmá que la configuración efectiva apunta a esa base y aplicá allí las migraciones. No ejecutes la suite completa con la configuración de datos habitual.

Con la base de pruebas ya preparada, desde `backend/`:
```bash
PYTHONPATH=.:tests ADMIN_EMAIL=admin@example.com .venv/bin/python -m pytest tests -q -ra
```

La variable `POSTGRES_DB` debe identificar esa base descartable durante las migraciones y las pruebas. Consultá [aislamiento, pasos y diagnóstico de la suite](../docs/backend-test-isolation.md) para preparar y retirar únicamente la base de pruebas.



### Afinado de umbrales de integridad con sesiones reales (T11)

Los umbrales de `app/services/integrity/thresholds.py` se ajustaron solo con datos sintéticos. Para afinarlos hacen falta sesiones reales etiquetadas:

1. En el `.env` del backend (solo development; production lo fuerza apagado): `INTEGRITY_DIAGNOSTICS_ENABLED=true` y, opcionalmente, `INTEGRITY_DIAGNOSTICS_DIR`. Reiniciá el backend. Con el flag apagado no se escribe nada ni se crea la carpeta.
2. Abrí `/app/browser-supervision-test` con el frontend en modo DEV, completá la calibración y elegí una **Etiqueta de prueba** (`normal`, `mirando_abajo`, `mirando_costado`, `mirando_arriba`, `ojos_abajo`, `boca_tapada`, `cara_tapada`, `camara_tapada`, `dos_personas`, `otra_voz`, `audio_dispositivo`, `hablando_yo`). Cada ventana de ~2,4 s se envía con esa etiqueta; cambiala cada vez que cambies de comportamiento y grabá un minuto o más de `normal` para medir falsas alarmas.
3. Cada ventana agrega una línea JSON a `<INTEGRITY_DIAGNOSTICS_DIR>/<trial_id>.jsonl` con la etiqueta, las anomalías y solo medidas numéricas (pose, mirada, parpadeo, boca, oclusión, cámara, RMS y segundos con voz, similitud de voz, hablantes, correlación y solapamiento labios-voz). Nunca se escriben imágenes, audio, embeddings, la huella de voz, la zona de mirada ni la referencia de oclusión. La etiqueta no se guarda en la bitácora.
4. Resumen por etiqueta (mín / p5 / mediana / p95 / máx, tasa de detección y falsas alarmas):

```bash
cd backend && .venv/bin/python scripts/integrity_tuning_report.py <INTEGRITY_DIAGNOSTICS_DIR>
```

Los archivos JSONL contienen datos de sesiones reales: borrá la carpeta al terminar.

## 7. Autenticación, sesiones y catálogo (HU-07, HU-08, HU-09, HU-10 y HU-12)

### Identidades y credenciales

- `POST /api/auth/oauth/google` es el único ingreso MEMBER. Requiere un ID token real, email verificado, audiencia `GOOGLE_CLIENT_ID`, emisor y expiración válidos. La identidad remota se verifica también en desarrollo; no existe bypass para tokens no firmados ni ingreso con GitHub/WhatsApp/OTP.
- `GOOGLE_CLIENT_ID` es público, no un client secret. Debe coincidir con el cliente Web del frontend y con la audiencia solicitada por los SDK nativos. Sin configurar, el endpoint devuelve 503, no una cuenta simulada.
- ADMIN utiliza exclusivamente `/api/admin/auth/login` con correo y contraseña. Google no autentica ni convierte cuentas ADMIN. Cualquier ADMIN activo puede gestionar otros ADMIN; el correo de seed no concede privilegios adicionales. Se conserva la protección contra auto-suspensión y la respuesta 404 para MEMBER/anónimos en rutas administrativas.
- El registro MEMBER crea una `wallets` vinculada, con saldo 0 en la misma transacción. `GET /api/auth/me` devuelve el saldo real. La migración agrega billeteras de saldo cero a miembros existentes, sin otorgar bonos ni habilitar operaciones monetarias.
- Refresh firma el nuevo par antes de consumir atómicamente el anterior. `revoked_tokens` guarda hashes SHA-256 y expiraciones, compartidos entre procesos; no almacena JWT en texto plano. Logout valida la propiedad del refresh antes de revocar credenciales.
- El ID token enviado a Google se redacta en los logs HTTPX; nunca registrar cuerpos de autenticación ni credenciales.

### Migrar y administrar el catálogo

Ejecutar `alembic upgrade head` antes de iniciar esta versión. La cadena agrega billeteras, revocaciones durables y jerarquía/unicidad del catálogo. Respaldar la base de datos antes de actualizar un entorno con datos; un downgrade de estas migraciones elimina las nuevas tablas/columnas y no sustituye un respaldo.

La migración de catálogo conserva los registros y rehúsa nombres normalizados duplicados entre categorías hermanas o habilidades de la misma categoría. Si informa `Duplicate normalized catalog names`, revisar los conflictos y decidir sus nombres antes de repetir: no los renombra, fusiona ni elimina automáticamente.

- Público: `GET /api/categories`, `GET /api/skills` y `GET /api/skills/{id}`. Solo se muestran registros activos con ancestros activos; filtrar una categoría incluye descendientes.
- Administración: se mantienen `/api/admin/catalog/categories` y `/api/admin/catalog/skills`. Las categorías incluyen `parent_id`; los movimientos validan referencias y rechazan ciclos con bloqueo transaccional.
- `DELETE` de categoría/habilidad desactiva, no borra físicamente. La eliminación de habilidades con miembros vinculados devuelve 409; `PATCH` con `is_active=false` conserva las asociaciones.

Las pruebas HTTP de esta entrega usan PostgreSQL aislado y mocks de Google. No acreditan disponibilidad de Google real, configuración de sus clientes ni ejecución en hardware nativo.
