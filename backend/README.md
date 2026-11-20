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
- **Análisis de video de dominadas (solo admin, prueba):** `POST /api/football/training/analyze-video` (multipart, campo `file`: mp4/webm/mov; requiere `ADMIN`, cualquier otro usuario o anónimo recibe `404`). Detecta el balón con MediaPipe EfficientDet-Lite0 (`efficientdet_lite0.tflite`, clase COCO "sports ball", Apache-2.0) fusionado con el detector clásico MOG2/Hough, cuenta toques y rachas (la racha se reinicia cuando el balón toca el suelo o tras más de 2,2 s sin toque; manda la racha más alta) y califica con el `level_classifier` activo o, si no hay, con el clasificador por reglas (Principiante/Intermedio/Avanzado/Experto, puntaje 1-100). Responde **siempre** `200` con `message: "Análisis de video completado."` y el resultado completo (`analysis_complete`, `ball_detected`, `detector`, `frames_analyzed`, `ball_frames`, `duration_seconds`, `total_touches`, `max_streak`, `streaks`, `ground_contacts`, `score_1_100`, `level`, `level_probabilities`, `confidence`, `model_version`, `notes`, `feedback`): un archivo ausente, vacío, de más de 200 MB, ilegible, sin balón o un fallo del detector devuelve 0 toques, nivel "Principiante", puntaje 1 y una nota que lo explica. Se analizan como máximo los primeros 180 s (nota si se recorta). No persiste el video, no consume intentos, no es una validación oficial y no envía nada a servicios externos; el flujo oficial sigue calificando 0 toques como "No calificado". El modelo se instala con el mismo `scripts/install_vision_models.py` (SHA-256 fijado, `FOOTBALL_MODELS`); si falta, se usa solo el detector clásico y se indica en `notes`. EfficientDet corre ~6 veces por segundo de video (≈30 ms por inferencia en CPU) y el detector clásico cubre los demás cuadros: ≈20 s de pared por minuto de video 720p. Pruebas: `tests/football/test_video_analysis.py`.

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
# Directorio padre de los workspaces temporales de cada ejecución. Vacío/sin definir = directorio temporal del SO.
# docker compose lo fija en "/sandbox-work" (volumen compartido) para que el daemon dind vea la misma ruta.
# SANDBOX_WORK_DIR=""



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

# --- Correo Transaccional (Recordatorios de Sesión, SMTP) ---
# Si EMAIL_ENABLED=True pero faltan credenciales, el envío se omite y se registra un error.
EMAIL_ENABLED=False
SMTP_HOST="smtp.gmail.com"
SMTP_PORT=587
SMTP_USERNAME=""
SMTP_PASSWORD=""
SMTP_STARTTLS=True
SMTP_TIMEOUT_SECONDS=15
EMAIL_FROM_ADDRESS="no-reply@skillmatch.io"
EMAIL_FROM_NAME="SkillMatch"
EMAIL_REPLY_TO=""

# URL base pública del frontend, usada para construir enlaces en emails
FRONTEND_BASE_URL="http://localhost:5173"

# --- Notificaciones Web Push (VAPID) ---
# WEB_PUSH_ENABLED=True exige VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY y VAPID_SUBJECT (mailto: o https://);
# si falta alguno, la aplicación no arranca (error de validación de Settings).
# Con WEB_PUSH_ENABLED=False el endpoint de clave pública responde 503 "Web Push no está configurado.".
# VAPID_PRIVATE_KEY acepta la clave en base64url o la ruta a un archivo PEM (comportamiento de pywebpush).
WEB_PUSH_ENABLED=False
VAPID_PUBLIC_KEY=""
VAPID_PRIVATE_KEY=""
VAPID_SUBJECT="mailto:admin@skillmatch.io"

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
# [SECRETO] JSON completo de la Service Account (prioridad); en Coolify se carga como variable secreta.
FIREBASE_CREDENTIALS_JSON=""
# Alternativa local si FIREBASE_CREDENTIALS_JSON está vacía: ruta absoluta o relativa al cwd / backend/.
FIREBASE_CREDENTIALS_PATH="firebase-credentials.json"
# Diagnóstico ADMIN: GET /api/admin/push/status y POST /api/admin/push/test.
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

## 8. Recordatorios de sesiones HU-38

Celery Beat registra el barrido `sessions.dispatch_due_reminders` cada cinco minutos. Los avisos in-app se generan siempre que correspondan; SMTP y Web Push permanecen deshabilitados hasta que el entorno configure sus credenciales.

- Enlaces: `FRONTEND_BASE_URL`.
- SMTP: `EMAIL_ENABLED`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_STARTTLS`, `SMTP_TIMEOUT_SECONDS`, `EMAIL_FROM_ADDRESS`, `EMAIL_FROM_NAME` y `EMAIL_REPLY_TO`.
- Web Push: `WEB_PUSH_ENABLED`, `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` y `VAPID_SUBJECT`.

`SMTP_USERNAME`, `SMTP_PASSWORD` y `VAPID_PRIVATE_KEY` se tipan con `SecretStr`; sus valores reales sólo deben existir en `.env` o en el gestor de secretos del despliegue. Consulte [la guía de QA HU-38](../docs/README_HU38_QA.md) para el semillero y las verificaciones controladas.

## 9. Laboratorio por habilidad

Requiere la migración `e7a4c1d9b352` (`alembic upgrade head`). Es aditiva: no reescribe filas existentes.

- **Criterios del catálogo:** cada criterio de `rubrics.criteria` es `{key, name, weight, description, metric_type, target}`. `key` lo genera el servidor si falta y se conserva en las actualizaciones (si se envía sin `key`, se reutiliza la del criterio guardado con el mismo nombre). `metric_type` ∈ `REFERENCE_REPLICATION` (predeterminado) | `BALL_TOUCH_STREAK` (`target` > 0 obligatorio = toques seguidos que valen el 100%). Si un nivel tiene criterios, sus pesos deben sumar 100 (±0.01); si no, la escritura responde 400 con «Los porcentajes de los criterios del nivel «<nombre>» deben sumar 100% (actual: <suma>%).». Los criterios guardados sin `key`/`metric_type` se leen con una clave determinista y el tipo predeterminado, sin reescribirlos.

- **Niveles estables:** al editar una habilidad, los niveles se actualizan en su lugar emparejados por `level_number`; solo se crean los números nuevos y se eliminan los ausentes. Los videos de un nivel eliminado quedan con `skill_level_id = NULL` (ON DELETE SET NULL).

- **Columnas nuevas:** `dataset_samples.skill_id` (FK `skills`, SET NULL), `skill_level_id` (FK `skill_levels`, SET NULL), `criterion_key` (64), `sample_role` (`TRAINING` | `REFERENCE`, predeterminado `TRAINING`), `analysis` (JSON, caché del análisis del motor) y `file_format` admite además `webm`/`mov`. `model_versions.skill_id` (FK `skills`, CASCADE) identifica el validador por habilidad (`nombre='skill_validator'`); un índice único parcial permite una sola versión activa por habilidad sin afectar a `level_classifier` ni a los modelos de flauta (sin `skill_id`).

- **Endpoints (solo ADMIN; MEMBER y anónimos reciben 404 «Recurso no encontrado»):**

  - `GET /api/admin/skill-lab/metric-types`: tipos de métrica con `requires_target`/`requires_reference`.

  - `GET /api/admin/skill-lab/skills/{skill_id}`: configuración tomada del catálogo (categoría, tipo de desafío, umbral, niveles, puntaje mínimo, criterios), conteos de videos por nivel/criterio, referencia vigente, `active_model` y `readiness.issues`.

  - `POST /api/admin/skill-lab/skills/{skill_id}/samples` (multipart): `file` (mp4/webm/mov, máx. 200 MB), `skill_level_id`, `sample_role`, `criterion_key` opcional, `participant_id` opcional y `signed_consent=true`. Un nuevo `REFERENCE` para el mismo nivel/criterio reemplaza al anterior (fila y archivo). El archivo se guarda en `storage/datasets/skill-lab/<categoría>/` y se replica en Garage S3 si hay credenciales.

  - `GET /api/admin/skill-lab/skills/{skill_id}/samples` (filtro opcional `sample_role`) y `DELETE /api/admin/skill-lab/samples/{sample_id}`.

  - `GET /api/admin/skill-lab/skills/{skill_id}/models`: versiones `skill_validator` de la habilidad.

  - `POST /api/admin/skill-lab/samples/{sample_id}/preview-url`: devuelve `{url, expires_at, content_type}` para reproducir una muestra (referencia o entrenamiento). `url` es `/api/admin/skill-lab/samples/{id}/file?token=…` (el frontend la resuelve contra la raíz de `VITE_API_URL`) y vence a los 10 minutos (`PREVIEW_TOKEN_TTL_SECONDS`, constante, sin variable de entorno). Muestra inexistente → 404 «Muestra no encontrada.»; sin copia local → 404 «El video de la muestra no está disponible.».

  - `GET /api/admin/skill-lab/samples/{sample_id}/file?token=…`: **única ruta del laboratorio sin cabecera `Authorization`** (un `<video>` no puede enviarla); se autoriza solo con el token, HMAC-SHA256 con `SECRET_KEY` sobre `skill-lab-preview|sample_id|expira`. Admite `Range` (206 + `Content-Range`) para adelantar el video, responde `Cache-Control: private, max-age=600` y `Content-Disposition: inline` con un nombre generado (`muestra-<id>.<ext>`, nunca el nombre original). La ruta del archivo sale solo de la muestra guardada y debe quedar dentro de `storage/`. Token inválido, vencido, de otra muestra o ausente, muestra inexistente o archivo faltante → 404 «Recurso no encontrado». El token viaja en la query string: puede quedar en logs de acceso durante sus 10 minutos de vigencia.

  - `POST /api/admin/skill-lab/skills/{skill_id}/train` (201): calibra el validador con los videos `TRAINING` vinculados a un nivel y crea la versión `v<n>` de esa habilidad como activa (desactiva la anterior en la misma transacción). Funciona con cero videos (tolerancias por defecto y la nota correspondiente). La tolerancia de un nivel o criterio siempre puede ampliarse, pero solo se reduce por debajo de la predeterminada (17°/28°) con al menos 5 videos genuinos de ese nivel/criterio (`MIN_SAMPLES_TO_TIGHTEN`), y nunca hasta reprobar a uno de esos videos genuinos si puede evitarse; con menos se agrega la nota «Con menos de 5 videos por nivel la tolerancia no se reduce; solo puede ampliarse.» cuando se habría reducido, y `fit`/`tolerances` registran `tightening_allowed`. `metricas` incluye las métricas del motor, `notes`, `engine_version` y `samples_per_level` (por id de nivel).

  - `POST /api/admin/skill-lab/skills/{skill_id}/validate` (multipart: `file`, `skill_level_id` opcional): siempre 200 con «Validación completada.» y el resultado de validación. Un video ilegible, vacío o de más de 200 MB devuelve `analysis_complete: false`, puntaje 0 y una nota; no se guarda nada y la copia temporal se elimina siempre. Un `skill_level_id` de otra habilidad responde 404 «Nivel no encontrado para esta habilidad.».

- **Motor (`app/skill_validation/`, local, sin red):** la pose usa MediaPipe Pose Landmarker (`pose_landmarker_full`, float16, en `MODELS_DIR`) y el balón reutiliza el tracker de fútbol. Si falta el modelo de pose, los criterios de réplica quedan `evaluable: false` con su motivo (nunca un aprobado inventado).

- **Caché de análisis:** al subir una muestra se analiza fuera del event loop y se guarda en `dataset_samples.analysis` (`analysis_ready`/`analysis_notes` en la respuesta); un fallo del análisis nunca rompe la subida. Las referencias solo necesitan pose; los videos `TRAINING` reciben todas las pasadas que mide la habilidad (pose si algún nivel replica una referencia, balón si algún nivel tiene `BALL_TOUCH_STREAK`), porque la calibración usa los videos de un nivel como negativos de los niveles superiores y el estimador de nivel combina ambas medidas; así, un video sin criterio de un nivel mixto recibe ambas pasadas. Entrenar y validar recalculan solo los análisis ausentes, de otra `engine_version` o sin una pasada necesaria.

- **Calibración persistida en la base de datos:** el JSON de calibración se guarda dentro de la fila (`model_versions.metricas.calibration`, oculto en las respuestas) y `ruta_onnx` vale `db:model_versions.metricas.calibration`; sobrevive a reinicios del contenedor sin depender del volumen de almacenamiento.

- **Reglas de puntaje (5 líneas):**

  1. Puntaje del nivel = Σ(peso × puntaje del criterio)/100; un nivel sin criterios es un criterio implícito `REFERENCE_REPLICATION` de peso 100.
  2. `REFERENCE_REPLICATION` compara ángulos articulares 3D con la referencia (espejo, ritmo y ángulo de cámara tolerados); `BALL_TOUCH_STREAK` = min(100, 100 × racha máxima / `target`).
  3. Sin referencia (o sin pose utilizable en ella) el criterio y el nivel quedan `evaluable: false` con `score: null`.
  4. `passed` = evaluable y puntaje ≥ `min_score`; `achieved_level` = el nivel aprobado de mayor `level_number`; `score` = el de ese nivel, si no el del nivel evaluable más bajo, si no 0.
  5. `approved` = hay `achieved_level` y `score` ≥ `min_approval_threshold` de la habilidad.

- **Punto de integración para el flujo del miembro:** `app.services.skill_lab_service.validate_skill_video(db, skill_id, video_path, target_level_id=None) -> dict`. Construye la especificación desde el catálogo, asegura los análisis de las referencias, usa la calibración activa (o la predeterminada), analiza solo las pasadas que requieren los niveles evaluados y devuelve el mismo resultado que `/validate`. No lanza excepciones por el video; una habilidad inexistente o un nivel ajeno lanzan `SkillMatchException` 404. La autenticación, la supervisión y el consumo de intentos del flujo del miembro quedan a cargo del llamador.

- **Preparación (`readiness`):** `ready_to_validate` exige que todos los niveles sean evaluables: pesos que suman 100, `target` en los criterios de balón y una referencia con pose utilizable donde se requiere (un video de referencia ilegible o sin persona genera un aviso para volver a subirlo). `active_model` es la versión activa guardada.