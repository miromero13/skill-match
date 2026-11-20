# SkillMatch con Docker Compose

Stack completo (API, Celery worker/beat, PostgreSQL, Redis, sandbox de programación aislado y SPA) con tres archivos:

| Archivo | Uso | Cómo se carga |
|---|---|---|
| `compose.yaml` | Base prod-like, autosuficiente | Siempre |
| `compose.override.yaml` | Desarrollo local: hot reload, puertos en `127.0.0.1`, Vite | Automático con `docker compose ...` |
| `compose.prod.yaml` | Overlay Coolify/VPS: entorno forzado, variables estrictas, límites | `-f compose.yaml -f compose.prod.yaml` |
| `docker.env.template` | Plantilla de variables → `.env` en la raíz (ignorado por Git) | `cp docker.env.template .env` |

Requisitos: Docker Engine con Compose **≥ 2.24** (`!reset`/`!override`). Imágenes: [`backend/Dockerfile`](../../backend/Dockerfile), [`frontend/Dockerfile`](../../frontend/Dockerfile).

---

## Arquitectura

| Servicio | Imagen | Rol | Redes | Volúmenes | Expuesto |
|---|---|---|---|---|---|
| `postgres` | `postgres:17-alpine` | Base de datos | `data` | `postgres-data` | dev: `127.0.0.1:${POSTGRES_HOST_PORT:-5433}` |
| `redis` | `redis:7.4-alpine` (AOF) | Broker/backend Celery | `data` | `redis-data` | dev: `127.0.0.1:${REDIS_HOST_PORT:-6380}` |
| `sandbox-docker` | `docker:28-dind` (**privileged**) | Daemon Docker aislado del sandbox, TLS en `:2376` | `sandbox` | `sandbox-docker-data`, `sandbox-certs-ca`, `sandbox-certs-client`, `sandbox-work` | — |
| `sandbox-init` | `docker:28-cli` (one-shot) | `docker pull $SANDBOX_DOCKER_IMAGE` en dind | `sandbox` | `sandbox-certs-client` (ro) | — |
| `init-volumes` | backend (one-shot, root) | `chown 10001` de `/app/storage` y `/sandbox-work` | ninguna | `backend-storage`, `sandbox-work` | — |
| `migrate` | backend (one-shot) | `alembic upgrade heads` (en prod: perfil `ops`) | `data` | — | — |
| `backend` | backend (`api`) | FastAPI/uvicorn `:8000` | `default`, `data`, `sandbox` | `backend-storage`, `sandbox-work`, `sandbox-certs-client` (ro) | dev: `127.0.0.1:8000` |
| `worker` | backend (`worker`) | Celery worker | `default`, `data` | `backend-storage` | — |
| `beat` | backend (`beat`) | Celery beat (recordatorios) | `default`, `data` | `backend-storage` | — |
| `frontend` | nginx-unprivileged (`runtime`) | SPA + proxy `/api/` y `/ws/` → `backend:8000` | `default` | — | base: `${FRONTEND_PORT:-8080}`; prod: solo `expose 8080`; dev: Vite `127.0.0.1:5173` |

Redes: `data` es **interna** (sin salida a Internet); `sandbox` une backend ↔ dind; `default` da salida (Google, Garage S3, proveedores LLM).

Orden de arranque: `postgres`/`redis` healthy → `init-volumes` → `sandbox-docker` healthy → `sandbox-init` → `migrate` → `backend` healthy → `frontend`. `worker` y `beat` esperan a `redis`, `migrate` e `init-volumes`.

---

## Desarrollo local (override automático)

```bash
cp docker.env.template .env      # valores locales seguros; completa GOOGLE_CLIENT_ID si usas login
docker compose up --build
```

| URL | Qué |
|---|---|
| http://localhost:5173 | SPA con Vite (HMR) |
| http://localhost:8000/docs | Swagger (solo `127.0.0.1`; nginx nunca expone `/docs`) |
| `127.0.0.1:5433` / `127.0.0.1:6380` | Postgres / Redis para herramientas locales (`POSTGRES_HOST_PORT` / `REDIS_HOST_PORT`; distintos de 5432/6379 para no chocar con un Postgres/Redis instalado en el host) |

- `ENVIRONMENT=development`, `DEBUG=True` y `UVICORN_RELOAD=true` salvo que `.env` los fije. `development` habilita la cabecera de pruebas `X-User-Id`: nunca uses el override en un servidor.
- `./backend/app` y `./backend/alembic` se montan en backend, worker, beat y migrate. Celery no recarga: `docker compose restart worker beat`.
- Nueva migración: `docker compose run --rm migrate` (o reinicia el stack).
- **Pesos de modelos:** el bind-mount de `./backend/app` ocultaría `/app/app/models/weights` (descargados al construir). Se monta encima el volumen `backend-weights`. Docker solo lo rellena con la imagen la primera vez (volumen vacío), así que en cada arranque `init-volumes` copia los modelos que falten desde la imagen recién construida (`cp -n`, sin sobrescribir). Para rehacerlo desde cero: `docker compose down && docker volume rm skillmatch_backend-weights`. Docker crea la carpeta vacía `backend/app/models/weights` en el host como punto de montaje (ignorada por Git).

## Prod-like en local

```bash
docker compose -f compose.yaml up --build     # sin override
```

SPA + API en http://localhost:8080 (`/api/` y `/ws/` por nginx). `ENVIRONMENT=production` y `DEBUG=False` por defecto. Cambiar `VITE_*` exige `docker compose -f compose.yaml build frontend`.

---

## Producción en Coolify (VPS)

1. **Recurso:** Docker Compose desde el repositorio, rama de despliegue, *Docker Compose Location* `/compose.yaml`.
2. **Comandos personalizados** (para aplicar el overlay):
   - Build: `docker compose -f compose.yaml -f compose.prod.yaml build`
   - Start: `docker compose -f compose.yaml -f compose.prod.yaml up -d`
3. **Variables** en la UI de Coolify (las del `docker.env.template`). Obligatorias (`${VAR:?}`, el despliegue falla si faltan o están vacías):

   | Variable | Ejemplo / regla |
   |---|---|
   | `SECRET_KEY` | `openssl rand -hex 32` |
   | `POSTGRES_PASSWORD` | `openssl rand -hex 24` (solo alfanumérico: la DSN no se URL-encodea) |
   | `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Administrador inicial (seed al arrancar) |
   | `ALLOWED_ORIGINS` | `https://app.tu-dominio.com` |
   | `FRONTEND_BASE_URL` | `https://app.tu-dominio.com` |
   | `VITE_API_URL` | `https://app.tu-dominio.com/api` (build arg: se incrusta en el bundle) |
   | `GOOGLE_CLIENT_ID` | Client ID Web de Google (también se usa para `VITE_GOOGLE_CLIENT_ID` si este queda vacío) |
   | `GARAGE_S3_ACCESS_KEY_ID`, `GARAGE_S3_SECRET_ACCESS_KEY` | Credenciales de Garage S3 |

   El overlay fuerza `ENVIRONMENT=production`, `DEBUG=False`, `VITE_APP_ENV=production` y `UVICORN_WORKERS` por defecto `2`.
4. **Dominio:** asígnalo al servicio `frontend`, puerto `8080` (p. ej. `https://app.tu-dominio.com:8080` en Coolify). Traefik termina TLS y enruta a `frontend:8080`; ningún otro servicio publica puertos.

### Primer despliegue (L6: migraciones explícitas)

```bash
P="docker compose -f compose.yaml -f compose.prod.yaml"
$P build
$P up -d postgres                          # solo la base de datos
$P --profile ops run --rm migrate          # alembic upgrade heads
$P up -d                                   # resto del stack
```

### Actualizaciones

1. **Backup** (siempre antes de migrar): ver [Backups](#backups).
2. `$P build`
3. Si la versión trae migraciones: `$P --profile ops run --rm migrate`.
4. `$P up -d` (Coolify lo hace al redeploy).

> Si Coolify no acepta los comandos personalizados o los tags `!reset`/`!override`, genera un único archivo sin resolver secretos: `docker compose -f compose.yaml -f compose.prod.yaml config --no-interpolate > compose.coolify.yaml` y úsalo como *Docker Compose Location*. Regenéralo cuando cambien los compose.

### Límites de memoria (`compose.prod.yaml`)

| Servicio | Límite | Motivo |
|---|---|---|
| `backend` | 4g | PyTorch + modelos de visión/audio por cada worker uvicorn |
| `worker` | 3g | Procesamiento de vídeo/fútbol |
| `sandbox-docker` | 2g | Daemon + ejecuciones de código concurrentes |
| `postgres` | 1g | |
| `migrate` | 1g | |
| `beat` | 512m | Solo planifica |
| `redis`, `sandbox-init` | 256m | |
| `frontend`, `init-volumes` | 128m | |

Son un punto de partida para un VPS de 8–16 GB; ajústalos con `docker stats`.

---

## Seguridad del sandbox de programación

- **dind aislado:** el código de los usuarios se ejecuta en un daemon Docker dedicado (`sandbox-docker`), nunca en el del host. El backend **no** monta `/var/run/docker.sock`.
- **`privileged: true` solo en `sandbox-docker`**, necesario para que dind ejecute su propio `dockerd`. Ningún otro servicio es privilegiado.
- **TLS mutuo** backend ↔ daemon: dind genera CA/certificados en `/certs` (`DOCKER_TLS_CERTDIR`), con SAN `sandbox-docker`. El backend usa `DOCKER_HOST=tcp://sandbox-docker:2376`, `DOCKER_TLS_VERIFY=1` y los certificados cliente montados **ro** desde `sandbox-certs-client`.
- **Contenedores de código** con `--network=none`, usuario `65532` y workspace montado solo lectura; la imagen (`SANDBOX_DOCKER_IMAGE`) la pre-descarga `sandbox-init`: la ruta de petición nunca hace pull.
- **Ruta compartida `/sandbox-work`:** `docker run -v <dir>:/workspace:ro` se resuelve en el filesystem del **daemon**, no del backend. Por eso el volumen `sandbox-work` está montado en la misma ruta en ambos y `SANDBOX_WORK_DIR=/sandbox-work` hace que el runner cree allí su directorio temporal (S8).
- El daemon está solo en la red `sandbox` (necesita salida para descargar la imagen del sandbox); no alcanza Postgres ni Redis.

## Modelos de IA

Los modelos de visión y de integridad de audio se descargan y verifican (SHA-256) **al construir** la imagen del backend con `scripts/install_vision_models.py` y `scripts/install_calibration_audio_models.py`; quedan en `/app/app/models/weights`. `install_vision_models.py` instala los modelos faciales (YuNet, SFace, MediaPipe FaceLandmarker) y el detector de balón MediaPipe EfficientDet-Lite0 (`efficientdet_lite0.tflite`) del análisis de video de fútbol; si este último falta, el análisis usa solo el detector clásico y lo indica en sus notas. También instala el modelo de pose corporal MediaPipe PoseLandmarker full (`pose_landmarker_full.task`, ~9 MB) del motor de validación de habilidades (`app/skill_validation`); si falta, los criterios de replicar el video de referencia quedan como no evaluables con una nota, nunca con un puntaje inventado. Tras agregar un modelo nuevo hay que reconstruir la imagen del backend (`docker compose build backend`) para que `init-volumes` lo copie al volumen `backend-weights`. No hay descargas en runtime. En desarrollo ver la nota del volumen `backend-weights`.

## Almacenamiento

- **Garage S3 es externo** (`GARAGE_S3_*`); el stack no levanta MinIO ni Garage.
- `backend-storage` (`/app/storage`): datasets, artefactos de fútbol y modelos entrenados, compartido por backend, worker y beat.

## Salud

| Servicio | Comprobación |
|---|---|
| `backend` | `GET /api/health` y exige `data.status == "healthy"` (el endpoint responde HTTP 200 incluso degradado) |
| `worker` | `celery inspect ping -d celery@$HOSTNAME` |
| `frontend` | `GET /healthz` (nginx) / raíz de Vite en dev |
| `postgres` / `redis` / `sandbox-docker` | `pg_isready` / `redis-cli ping` / `docker info` |
| `beat` | Sin healthcheck (no expone interfaz); revisar logs |

Comprobación extremo a extremo: `curl -s http://localhost:8080/api/health` → `statuscode: 200`, `data.status: "healthy"`.

---

## Operación

```bash
P="docker compose -f compose.yaml -f compose.prod.yaml"   # en local: docker compose
$P ps                                   # estado y salud
$P logs -f backend worker               # logs (json-file, 10m x 5 por servicio)
$P exec backend python -c "print('ok')" # shell en el contenedor
$P up -d --scale worker=2               # más workers Celery (o CELERY_CONCURRENCY)
```

### Backups

```bash
# Backup lógico comprimido (formato custom)
$P exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > skillmatch-$(date +%F-%H%M).dump

# Restauración (sobre una base vacía)
$P exec -T postgres sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists' < skillmatch-AAAA-MM-DD-HHMM.dump
```

Incluye también el volumen `backend-storage` si guarda datos que no estén en Garage S3.

## Solución de problemas

| Síntoma | Causa probable / acción |
|---|---|
| `required variable X is missing a value` | Falta en `.env` o en Coolify (ver variables obligatorias) |
| `backend` unhealthy | `logs backend`; `data.status` ≠ `healthy` = sin conexión a Postgres |
| Error de autenticación de Postgres tras cambiar la contraseña | La contraseña solo se aplica al crear `postgres-data`; cámbiala con `ALTER USER` o recrea el volumen (borra datos) |
| `sandbox-init` falla | `logs sandbox-docker`; TLS/certificados o sin salida a Internet para el pull |
| Ejecuciones de código fallan con error de Docker | Verifica `$P exec backend docker info` (usa el daemon dind por TLS) |
| `permission denied` en `/app/storage` | `init-volumes` no terminó: `$P logs init-volumes` |
| La SPA llama a otra URL de API | `VITE_API_URL` se incrusta al construir: reconstruye `frontend` |
| CORS bloqueado | Añade el origen exacto a `ALLOWED_ORIGINS` |
| Vite no recarga en macOS/Windows | Reinicia `frontend`; los eventos de ficheros del bind-mount pueden retrasarse |
| `port is already allocated` en 5433/6380 | Otro proceso usa el puerto: cambia `POSTGRES_HOST_PORT` / `REDIS_HOST_PORT` en `.env` |
| Build falla con `read-only file system` (`metadata_v2.db`, `meta.db`) o `no space left on device` | El disco del Mac se llenó y la VM de Docker Desktop pasó a solo lectura. Libera espacio (la imagen del backend pesa ~2,3 GB y la build necesita ~10 GB libres), reinicia Docker Desktop, `docker builder prune -af` y reconstruye |
| `backend` en loop con `ModuleNotFoundError: No module named 'ml'` | El backend importa el paquete `ml/` de la raíz del repo; compose lo pasa como contexto de build `ml`. Fuera de compose: `docker build --build-context ml=./ml backend` |
| `face_landmarker ... libEGL.so.1: cannot open shared object file` | La imagen necesita `libegl1` y `libgles2` (MediaPipe los carga aun en CPU); reconstruye el backend |
| Build falla en `[backend models 4/4]` (`install_vision_models.py` / `install_calibration_audio_models.py`, exit 1) | Descarga de modelos cortada por la red (GitHub / Google Storage), típico en la primera build mientras compose descarga imágenes y ejecuta `npm ci` en paralelo. El paso reintenta 3 veces; si aún falla, verificá la conexión y reconstruí (`docker compose build backend`): los modelos ya verificados quedan en caché |
| El admin creado no es el esperado | El seed usa `ADMIN_EMAIL`/`ADMIN_PASSWORD` del `.env` de la **raíz** (no `backend/.env`) y solo crea el admin si ese correo no existe. Corrigí el `.env` y `docker compose up -d backend` |
| `alembic upgrade head` → `Multiple head revisions are present` | El historial tiene varias heads sin merge; el rol `migrate` usa `alembic upgrade heads` |
| `npm run build` falla por tipos en `src/test` | La imagen solo type-checkea el código que se publica (`tsconfig.app.json` + `tsconfig.node.json`); los errores de tests se ven con `npm run typecheck` |

## Brechas conocidas

- **ASR teórico:** el modelo Whisper (`app/models/weights/theory-whisper/*`) no tiene instalador ni se provisiona en la imagen: los endpoints de ASR responden 503.
- **Catálogo inicial:** `ensure_initial_catalog` nunca se invoca; el catálogo no se siembra al arrancar.
- **`/api/health`** responde HTTP 200 incluso degradado; compose valida el cuerpo, pero monitores externos deben hacer lo mismo.
- **Content-Security-Policy** aún no se envía desde nginx.
- **Fuga de contenedores del sandbox ante timeout:** `DockerSandboxRunner` mata el proceso del CLI `docker` con SIGKILL al exceder `time_limit_ms`, pero el contenedor sigue corriendo dentro del daemon (comprobado: un `while True` quedó al 100% de CPU indefinidamente). Es previo a este stack (pasa igual contra el Docker del host). Mientras no se corrija, limpiar con `$P exec sandbox-docker docker ps` / `docker rm -f <id>`.
