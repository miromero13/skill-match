# SkillMatch — Resumen General del Repositorio (`repo-overview.md`)

Este documento resume la arquitectura, estructura de directorios, modelo de autenticación, persistencia de datos y convenciones de ingeniería vigentes en el monorepo de **SkillMatch**. Sirve como referencia base antes de extender cualquier módulo (incluyendo el pipeline de validación de habilidad de fútbol con IA propia).

---

## 1. Estructura del Monorepo

El repositorio sigue una arquitectura cliente-servidor desacoplada en dos directorios principales y una carpeta de documentación y gobernanza:

```text
skill-match/
├── AGENTS.md                 # Contrato maestro de gobernanza para agentes e ingenieros
├── CONTRIBUTING.md           # Flujo Git, ramas, Conventional Commits en inglés
├── docs/                     # Documentación de arquitectura (C4, backend, frontend, historias)
├── odd/tasks/                # Especificaciones y seguimiento de tareas (Organic Driven Development)
├── backend/                  # API REST y WebSockets con FastAPI + SQLAlchemy 2.0 Async
│   ├── alembic/              # Migraciones de esquema de base de datos PostgreSQL
│   ├── app/
│   │   ├── api/              # Routers HTTP organizados por dominio (admin, auth, skills, users, ai)
│   │   ├── core/             # Configuración Pydantic Settings, JWT, middlewares, excepciones
│   │   ├── db/               # Motor asyncpg, AsyncSessionLocal, Base declarativa y seeds
│   │   ├── football/         # Módulo de validación de fútbol con IA propia (Fase 0+)
│   │   ├── models/           # Entidades ORM SQLAlchemy 2.0 (Mapped / mapped_column)
│   │   ├── schemas/          # Contratos Pydantic v2 y sobre estándar APIResponse[T]
│   │   └── services/         # Lógica de negocio y almacenamiento
│   ├── tests/                # Suite de pruebas automatizadas con pytest y pytest-asyncio
│   ├── env.template          # Plantilla obligatoria de variables de entorno
│   └── pyproject.toml        # Dependencias y configuración de ruff, mypy y pytest
└── frontend/                 # SPA Web & Móvil con React 19 + TypeScript + Vite + Capacitor
    ├── src/
    │   ├── components/       # Componentes reutilizables y sistema de diseño Shadcn/ui (preset Mist)
    │   ├── features/         # Módulos funcionales específicos (ej. football-validation)
    │   ├── layouts/          # Layouts de plataforma pública, miembro y administrador
    │   ├── pages/            # Vistas de página conectadas a React Router v7
    │   ├── routes/           # Definición de rutas y guardias (AdminRouteGuard)
    │   ├── services/         # Cliente HTTP (apiClient) e integración con el backend
    │   ├── stores/           # Estado global modular con Zustand v5
    │   ├── types/            # Contratos TypeScript estrictos (sin `any`)
    │   └── test/             # Pruebas unitarias y de componentes con Vitest + Testing Library
    └── package.json
```

---

## 2. Autenticación, Autorización y Seguridad (RBAC Estricto)

El sistema implementa un control de acceso basado en roles (**RBAC**) con únicamente dos roles canónicos definidos en `app/models/user.py` (`UserRole`):

1. **`MEMBER` (Miembro de la comunidad — aprendiz e instructor):**
   - Autenticación exclusiva mediante proveedores OAuth2/OIDC y OTP (**Google**, **GitHub**, **WhatsApp**).
   - No utiliza contraseñas locales.
2. **`ADMIN` (Administrador de la plataforma):**
   - Autenticación exclusiva por correo electrónico y contraseña (`bcrypt` nativo en `app/core/security.py`).
   - El administrador inicial se aprovisiona automáticamente en el arranque (`lifespan`) desde variables de entorno (`ADMIN_EMAIL`, `ADMIN_PASSWORD`).

### Tokens JWT y Dependencias (`app/core/deps.py`)
- Los tokens JWT (`HS256`) incluyen los claims `"sub"` (UUID del usuario), `"role"` (`"MEMBER"` o `"ADMIN"`), `"type"` (`"access"` o `"refresh"`), `"jti"` (UUIDv4 único para rotación y revocación en memoria) y `"exp"`.
- **`get_current_user`**: Valida el token `Bearer` y devuelve la instancia `User` activa y no bloqueada (`is_active=True`, `is_locked=False`).
- **`get_current_admin_user` / `require_admin_role` (Política de Ofuscación 404):**
  - Cualquier intento de acceso a rutas o endpoints administrativos (`/api/admin/...`, `/api/ai/datasets/...` o `/admin/...` en frontend) por parte de un usuario anónimo o con rol `MEMBER` devuelve estrictamente **`statuscode: 404`** (`"Recurso no encontrado"`), nunca `401` ni `403`.

---

## 3. Base de Datos y Migraciones

- **Motor:** PostgreSQL accedido de forma 100% asíncrona mediante **SQLAlchemy 2.0** (`AsyncSession`, `asyncpg`) configurado en `app/db/session.py`.
- **Base Declarativa:** `Base` y `TimestampMixin` (`created_at`, `updated_at` con `timezone=True`) en `app/db/base.py`.
- **Entidades Existentes:**
  - `users`: Usuarios miembros y administradores (`User`, `UserRole`).
  - `categories`, `challenge_types`, `skills`, `skill_levels`, `rubrics`: Catálogo maestro de habilidades y modalidades de evaluación (`CODE`, `AUDIO`, `VIDEO_POSE`, `THEORY`).
  - `user_learning_skills`, `teaching_skills`, `skill_evidences`: Habilidades que los miembros desean aprender o enseñar y sus evidencias portafolio.
  - `dataset_samples`: Muestras multimedia recolectadas para entrenamiento de modelos internos con validación SHA-256 y consentimiento firmado.
- **Migraciones:** Gestionadas con **Alembic** (`backend/alembic/`). Cada cambio de esquema requiere una nueva revisión sin modificar migraciones históricas ya aplicadas.

---

## 4. Convenciones Innegociables del Proyecto

1. **Sobre Estándar `APIResponse[T]` (`app/schemas/response.py`):**
   Toda respuesta HTTP (éxito o error manejado en `app/core/exceptions.py`) respeta la estructura:
   ```json
   {
     "statuscode": 200,
     "message": "Descripción legible para mostrar directamente en UI",
     "data": {},
     "count": 0
   }
   ```
   Está prohibido devolver estructuras heterogéneas o usar claves `"error"` o `"detail"` sueltas.
2. **Prefijos de Rutas API:**
   La regla del repositorio (`AGENTS.md`) establece rutas bajo `/api/...` (ej. `/api/football/...`). Para mantener compatibilidad con herramientas o clientes que invoquen `/api/v1/football/...` según el instructivo de fútbol, el router se expone en `/api/football` con alias compatible en `/api/v1/football`.
3. **Almacenamiento S3 Propio (Garage S3 en Coolify):**
   Los archivos multimedia y fragmentos de validación se almacenan en infraestructura propia compatible con S3 (**Garage S3** desplegado en VPS con Coolify, o fallback local estructurado en entorno de pruebas sin red).
4. **Cero IA de Terceros:**
   Prohibido el uso de APIs comerciales externas (OpenAI, Anthropic, Gemini) o modelos con licencias restrictivas (como Ultralytics YOLO AGPL). Todo el pipeline usa visión clásica (OpenCV, NumPy, SciPy, FilterPy), procesamiento de audio (`librosa`, `soundfile`) y modelos propios entrenados desde cero (PyTorch, scikit-learn, XGBoost, ONNX Runtime) con plantillas determinísticas para retroalimentación.
5. **Gobernanza de Variables de Entorno:**
   Todo secreto usa `SecretStr` en `app/core/config.py` y toda variable nueva se documenta simultáneamente en `backend/env.template` y `backend/README.md`.
6. **Frontend React 19 + Shadcn/ui (Preset Mist):**
   Tipado TypeScript estricto sin `any`, estado en tiendas atómicas de **Zustand**, y uso obligatorio de los componentes oficiales en `frontend/src/components/ui/`.
