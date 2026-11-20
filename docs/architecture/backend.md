# SkillMatch — Arquitectura Detallada del Backend

*Especificación técnica, modularidad, persistencia asíncrona y estándares de ingeniería para la API de SkillMatch.*

---

## 1. Principios de Arquitectura del Backend

El backend de SkillMatch está construido con **Python 3.12+**, **FastAPI**, **SQLAlchemy 2.0 (asyncpg)** y **Alembic**, adoptando un diseño modular orientado a dominios limpios (*Clean Domain-Driven Modular Architecture*):

1. **Totalmente Asíncrono:** Ningún bloqueo de I/O en endpoints de base de datos o llamadas de red (`async def` en routers y controladores con `await` explícito).
2. **Esquema de Respuesta Unificado Obligatorio:** Toda salida hacia el cliente implementa el modelo `APIResponse[T]`.
3. **Manejo Centralizado de Excepciones:** No se permiten respuestas 500 crudas ni formatos 422 estándar de FastAPI que expongan la estructura interna sin envolver.
4. **Separación de Responsabilidades:**
   - `app/api/`: Capa de transporte HTTP, validación de schemas de entrada y autorización.
   - `app/core/`: Configuración (`pydantic-settings`), seguridad JWT, middlewares y manejadores de error.
   - `app/db/`: Inicialización del engine asíncrono, pool de conexiones y Base declarativa.
   - `app/models/`: Definición de entidades ORM SQLAlchemy.
   - `app/schemas/`: Contratos Pydantic de entrada, salida y el sobre genérico `APIResponse`.
   - `app/services/`: Lógica de negocio pura (motor de matching, orquestación de sandbox, validación de cuotas).

---

## 2. Contrato de Respuesta Unificado (APIResponse)

### 2.1 Definición Pydantic
```python
from typing import Generic, TypeVar, Optional, Any
from pydantic import BaseModel, Field

DataT = TypeVar("DataT")

class APIResponse(BaseModel, Generic[DataT]):
    statuscode: int = Field(..., description="Código de estado HTTP de la respuesta")
    message: str = Field(..., description="Mensaje explicativo para el usuario o sistema")
    data: Optional[DataT] = Field(default=None, description="Carga útil de la respuesta")
    count: Optional[int] = Field(default=None, description="Cantidad total de registros (en listados)")

    class Config:
        from_attributes = True
```

### 2.2 Política de Errores y Excepciones
Un middleware / handler global captura:
- **`StarletteHTTPException`:** Mapea el código y mensaje en `statuscode` y `message`, con `data=None`.
- **`RequestValidationError` (422):** Convierte las validaciones de Pydantic en un mensaje legible, sin reflejar valores enviados ni mensajes arbitrarios de validadores. Devuelve `data: null` y omite `count`, conforme al contrato ratificado para HU-16 y `AGENTS.md`.
- **`Exception` no controlada (500):** Loguea el traceback en consola con UUID de correlación y devuelve `statuscode: 500` con `message: "Error interno del servidor"` protegiendo los secretos de la infraestructura.

Todos los manejadores de error (dominio, HTTP, validación y errores inesperados) devuelven únicamente `statuscode`, `message` y `data: null`. `count` queda reservado para listados paginados. Las excepciones HTTP conservan sus cabeceras de protocolo, por ejemplo `WWW-Authenticate` y `Retry-After`.

---

## 3. Persistencia de Datos y Migraciones

### 3.1 SQLAlchemy 2.0 Asíncrono con asyncpg
- Se utiliza la URL de conexión `postgresql+asyncpg://...`.
- Pool de conexiones parametrizado (`pool_size`, `max_overflow`, `pool_pre_ping=True`).
- Inyección de dependencias para sesiones de base de datos:
  ```python
  async def get_db() -> AsyncGenerator[AsyncSession, None]:
      async with AsyncSessionLocal() as session:
          try:
              yield session
              await session.commit()
          except Exception:
              await session.rollback()
              raise
  ```

### 3.2 Alembic en Modo Asíncrono
- Configurado con `asyncio.run(run_async_migrations())` en `alembic/env.py`.
- Integrado con la metadata de `Base` de SQLAlchemy para autogeneración limpia de migraciones (`alembic revision --autogenerate`).

---

## 4. Estructura de Carpetas del Backend (`backend/`)

```text
backend/
├── alembic/                      # Configuración y versiones de migraciones
│   ├── versions/                 # Scripts individuales de migración
│   ├── env.py                    # Runner asíncrono de Alembic
│   └── script.py.mako            # Plantilla para nuevas migraciones
├── app/
│   ├── api/                      # Controladores REST organizados por dominio
│   │   ├── admin/                # Endpoints exclusivos para ADMIN (política 404 para miembros)
│   │   ├── auth/                 # Google OAuth para MEMBER, correo/clave para ADMIN
│   │   ├── evaluations/          # Evaluaciones teóricas, Sandbox de código, audio, video
│   │   ├── health/               # Endpoint /api/health (chequeo app y DB)
│   │   ├── matching/             # Matching bilateral y grafos triangulares
│   │   ├── passports/            # Consultas públicas de pasaporte QR
│   │   ├── sessions/             # Agendamiento, PIN presencial, WebRTC
│   │   ├── skills/               # Catálogo oficial, oferta y demanda
│   │   ├── users/                # Perfiles, disponibilidad semanal, bloqueos
│   │   └── wallet/               # SkillPoints, transacciones, escrow y cashout
│   ├── core/                     # Núcleo de la aplicación
│   │   ├── config.py             # Settings con pydantic-settings y validación de .env
│   │   ├── exceptions.py         # Clases de excepción personalizadas y handlers de APIResponse
│   │   ├── middlewares.py        # CORS, compresión GZip, request timing, security headers
│   │   └── security.py           # Hashing de contraseñas (Admin), JWT encode/decode con claim role
│   ├── db/                       # Capa de base de datos
│   │   ├── base.py               # DeclarativeBase común
│   │   └── session.py            # AsyncEngine y AsyncSessionLocal
│   ├── models/                   # Modelos ORM SQLAlchemy
│   │   ├── __init__.py           # Exportación centralizada para Alembic
│   │   ├── user.py
│   │   ├── skill.py
│   │   ├── evaluation.py
│   │   ├── session.py
│   │   └── wallet.py
│   ├── schemas/                  # Contratos Pydantic
│   │   ├── __init__.py
│   │   ├── response.py           # Definición de APIResponse[T]
│   │   └── health.py             # Schemas de salud del sistema
│   ├── services/                 # Lógica de dominio pura y desacoplada
│   └── main.py                   # Fábrica de la aplicación FastAPI y registro de eventos
├── tests/                        # Suite de pruebas automatizadas
│   ├── conftest.py               # Fixtures asíncronas con pytest-asyncio y httpx.AsyncClient
│   ├── test_api_response.py      # Verificación estricta de la envoltura APIResponse y 422
│   └── test_health.py            # Verificación de salud y conectividad a base de datos
├── .env.example                  # Plantilla de variables de entorno documentada
├── alembic.ini                   # Archivo de configuración de Alembic
├── Dockerfile                    # Multi-stage Dockerfile optimizado
├── pyproject.toml                # Definición de dependencias y empaquetado (compatible con uv)
└── README.md                     # Guía completa de instalación local y con Docker
```

---

## 5. Middleware y Configuración de Red
- **CORS:** Lista blanca de orígenes definible mediante variable de entorno `ALLOWED_ORIGINS` (por defecto `http://localhost:3000`, `http://localhost:5173`, etc.).
- **GZip:** Compresión automática de cargas útiles mayores a 1000 bytes.
- **Seguridad HTTP:** Cabeceras preventivas `X-Content-Type-Options: nosniff` y `X-Frame-Options: DENY`.
- **Docs Swagger UI:** Accesible en `/docs`, OpenAPI spec en `/openapi.json` con metadatos del proyecto y descripción de seguridad.

---

## 6. Consulta de opciones de agendamiento HU-38

`GET /api/matches/{match_id}/session-options` es una consulta productiva previa a la creación de sesiones. El router de matches valida JWT MEMBER y delega el cálculo a `exchange_session_service`, que conserva las reglas de disponibilidad y conflictos junto al agregado de sesiones.

- No reemplaza `POST /api/sessions` ni realiza escrituras.
- Solo un participante de un match `confirmed` puede consultarla; recursos ajenos se ofuscan con 404.
- Resuelve `instructor_id`, `learner_id` y `teaching_skill_id` desde relaciones persistidas, nunca desde nombres enviados por el cliente.

### Recordatorios y exportación manual de calendario

- Las políticas puras de HU-38 definen avisos a 24 horas y 1 hora, solo para sesiones futuras `ACCEPTED`. La identidad determinística combina sesión, destinatario, umbral e inicio, por lo que un reintento conserva identidad y una reprogramación invalida el horario anterior.
- `GET /api/sessions/{session_id}/calendar-export` aplica JWT MEMBER, pertenencia y estado `ACCEPTED`; devuelve mediante `APIResponse` contenido iCalendar UTC y una URL manual de Google Calendar.
- Esta exportación no solicita scopes Calendar, no reutiliza el OAuth de login, no almacena refresh tokens y no se presenta como sincronización automática.
- `session_reminder_dispatches` conserva una identidad única por sesión, usuario, umbral e inicio. Celery Beat ejecuta `sessions.dispatch_due_reminders` cada cinco minutos; el servicio inserta el despacho y la notificación durable en una transacción.
- Después del commit, el worker publica únicamente IDs de notificación por el canal Redis `skillmatch:notification-committed`. Cada instancia FastAPI consume ese canal y delega en el publicador WebSocket existente. Si Redis/WebSocket falla, la notificación durable permanece disponible en la bandeja.
- La instancia Celery vive en `app/core/celery_app.py` y es compartida por sesiones y evaluación de fútbol; solo debe ejecutarse una instancia Beat para evitar barridos redundantes, aunque las constraints mantienen la idempotencia.
- El correo transaccional es un canal derivado y opcional: `session_reminder_email_deliveries` conserva una identidad única por despacho/evento, estado, intentos y resultado. Solo se crea cuando la preferencia de correo del destinatario está activa.
- El transporte `SMTPEmailSender` usa STARTTLS, credenciales `SecretStr` y plantillas determinísticas de texto/HTML. Celery procesa filas `PENDING` con bloqueo `FOR UPDATE SKIP LOCKED`, invalida sesiones canceladas/reprogramadas y limita a tres intentos.
- El `Message-ID` estable reduce duplicados en reintentos. SMTP no ofrece garantía exactly-once si el proceso cae después de la aceptación del proveedor y antes del commit; esa ambigüedad se documenta y no se presenta como entrega confirmada al destinatario.
- Web Push se limita al navegador/PWA. `GET /api/notifications/push/public-key`, `POST /api/notifications/push/subscriptions` y `DELETE /api/notifications/push/subscriptions/{subscription_id}` requieren JWT de un `MEMBER` activo; el push nativo Capacitor mediante FCM/APNs permanece fuera de HU-38.
- Una cuenta puede registrar varios dispositivos. El hash SHA-256 del endpoint identifica globalmente la capability URL: un reintento del mismo propietario actualiza/reactiva la suscripción, otro propietario recibe `409` y una revocación ajena o repetida responde `404`.
- La API nunca devuelve el endpoint completo ni `p256dh`/`auth`; sólo expone una huella diagnóstica. `VAPID_PRIVATE_KEY` es `SecretStr`, reside exclusivamente en el entorno y Web Push permanece inactivo mientras `WEB_PUSH_ENABLED=False` o falte configuración.
- `session_reminder_web_push_deliveries` audita cada combinación de evento y suscripción con identidad determinística, estado e intentos. El barrido Celery revalida la sesión, el horario, la preferencia Push y la vigencia del dispositivo justo antes de transmitir.
- El adaptador `pywebpush` cifra y firma localmente mediante VAPID y se ejecuta fuera del event loop. `404/410` desactivan la suscripción; `429` y `5xx` reintentan hasta tres veces; fallos permanentes o de configuración no se reintentan. La restricción única y `FOR UPDATE SKIP LOCKED` evitan duplicados ordinarios entre workers.
- Proyecta 14 días de franjas de 30/60 minutos y devuelve únicamente combinaciones compatibles de timezone, modalidad, disponibilidad, buffer, sesiones activas y bloqueos HU-26.
- El frontend consume una dirección y una franja sin recalcular reglas de dominio; `POST /api/sessions` vuelve a validar todo transaccionalmente para evitar condiciones de carrera.
