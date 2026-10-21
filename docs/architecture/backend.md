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
- **`RequestValidationError` (422):** Convierte el array de validaciones de Pydantic en un mensaje legible y deposita el detalle estructurado de los campos fallidos en `data`.
- **`Exception` no controlada (500):** Loguea el traceback en consola con UUID de correlación y devuelve `statuscode: 500` con `message: "Error interno del servidor"` protegiendo los secretos de la infraestructura.

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
│   │   ├── auth/                 # OAuth Google/GitHub, OTP WhatsApp, Login Admin
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
