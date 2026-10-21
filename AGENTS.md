# SkillMatch — Instrucciones Maestras y Gobernanza de Agentes (AGENTS.md)

Este documento es el **contrato maestro de desarrollo asistido por Inteligencia Artificial** para el proyecto **SkillMatch**. Todo agente autónomo, subagente o modelo que intervenga en este repositorio debe respetar de forma irrestricta los principios, reglas y arquitecturas aquí plasmadas.

---

## 1. Principios Fundamentales del Sistema

### 1.1 Restricción Estricta de IA Propia (Zero Third-Party LLM API)
- **Prohibido:** OpenAI, Anthropic, Gemini o cualquier proveedor comercial de LLMs / visión / audio en la nube.
- **Implementación obligatoria:** Todo modelo de inferencia y extracción de características corre en infraestructura propia con librerías open-source:
  - **Programación:** AST de Python (`ast`), sandbox Docker rootless y evaluación de complejidad ciclomática.
  - **Música:** Procesamiento espectral de audio (`librosa`) y redes convolucionales en `PyTorch`.
  - **Fútbol / Deportes:** Visión artificial (`OpenCV`) y estimación de pose en `PyTorch`.
- **Feedback determinístico:** Las devoluciones pedagógicas y preguntas de defensa se generan mediante reglas y plantillas algorítmicas basadas en métricas numéricas exactas, nunca con prompts generativos en la nube.

### 1.2 Formato Estándar de Respuesta API (APIResponse)
Todas las respuestas HTTP emitidas por el backend siguen estrictamente el esquema unificado:
```json
{
  "statuscode": 200,
  "message": "Operación completada exitosamente",
  "data": {},
  "count": 0
}
```
- `statuscode` (int): Código HTTP correspondiente (200, 201, 400, 404, 500, etc.).
- `message` (str): Mensaje descriptivo de la operación o error. El frontend **debe** mostrar textualmente este texto en sus alertas o toasts.
- `data` (any | null): Contenido de retorno o `null` en caso de error o acciones sin payload.
- `count` (int, opcional): Número total de elementos devueltos únicamente en listados paginados.
- **Prohibido:** Usar un campo `error` o estructuras heterogéneas.

### 1.3 Modelo Canónico de Roles y Accesos (RBAC Estricto)
Se definen únicamente dos roles en todo el ecosistema (backend y frontend):
- `MEMBER`: Miembro de la comunidad (aprendiz e instructor). Autenticación **exclusiva** vía proveedores sociales y OTP (**Google**, **GitHub**, **WhatsApp**). Sin contraseñas locales ni recuperación de contraseña.
- `ADMIN`: Administrador de la plataforma. Autenticación **exclusiva** por correo y contraseña (seed inicial + creación manual por otro ADMIN).
- **Claim dinámico en JWT:** `"role": user.role.value` (`"MEMBER"` o `"ADMIN"`).
- **Política de Ofuscación 404 (Security by Obfuscation):** Cualquier intento de acceso no autorizado por un `MEMBER` o visitante anónimo a rutas o endpoints administrativos (`/admin/...` o `/api/admin/...`) debe retornar **`statuscode: 404`** ("Recurso no encontrado"), jamás un `403 Forbidden`. El usuario no debe saber que la funcionalidad existe.

---

## 2. Mapa de Documentación Arquitectónica

Antes de generar o modificar código, el agente debe consultar los siguientes documentos rectores:
1. **Arquitectura Global del Sistema:** [`docs/architecture/system.md`](docs/architecture/system.md)
   - Visión C4, diagramas de contenedores, topología de despliegue, seguridad integral y flujos de datos.
2. **Arquitectura de Backend:** [`docs/architecture/backend.md`](docs/architecture/backend.md)
   - FastAPI, SQLAlchemy 2.0 asíncrono, Alembic, Docker Sandbox, endpoints `/api/...`, validaciones Pydantic y middlewares.
3. **Arquitectura de Frontend & Mobile:** [`docs/architecture/frontend.md`](docs/architecture/frontend.md)
   - React 19 + TypeScript, Vite, Zustand stores, Shadcn/ui (preset Mist), Capacitor y diseño 100% responsive.
4. **Contexto de Negocio:** [`docs/CONTEXT_PROJECT.md`](docs/CONTEXT_PROJECT.md)
5. **Requisitos Funcionales:** [`docs/FUNCTIONAL_REQUIREMENTS.md`](docs/FUNCTIONAL_REQUIREMENTS.md)
6. **Historias de Usuario (Jira Ready):** [`docs/USER_STORIES.md`](docs/USER_STORIES.md)
7. **Prototipos y Vistas UI:** [`docs/prototipo/`](docs/prototipo/) (assets exportados en PNG y archivo `.op`).

---

## 3. Guías de Actuación para Agentes de Código

### 3.1 Estándares de Backend (Python / FastAPI)
- **Versión de Python:** Python 3.12+ (compatible con 3.14).
- **Rutas sin versionado:** Usar `/api/...` (ej. `/api/health`, `/api/auth/oauth/google`, `/api/admin/catalog`).
- **Manejo Centralizado de Excepciones:** Todas las excepciones (`HTTPException`, `RequestValidationError` y excepciones inesperadas de sistema) deben transformarse en el sobre `APIResponse` con su correspondiente código.
- **Operaciones Asíncronas:** Uso mandatorio de `async/await` en routers, servicios y consultas a base de datos con `AsyncSession`.
- **Estructura Modular Limpia:** Separación estricta entre `api` (controladores), `core` (seguridad, config, middleware), `db` (sesión SQLAlchemy), `models` (entidades ORM), `schemas` (contratos Pydantic) y `services` (lógica de dominio).

### 3.2 Estándares de Frontend (React / TypeScript / Zustand / Tailwind)
- **Tipado estricto:** TypeScript estricto sin uso de `any`.
- **Estética y Design System:** Shadcn/ui con preset **Mist** (paleta de colores fríos, verde esmeralda institucional, tipografía Inter).
- **Gestión de Estado:** Tiendas atómicas y modulares con **Zustand**. No inflar estados globales innecesarios.
- **Responsividad:** 100% responsive en móvil, tablet y desktop; en móvil la navegación principal reside en la barra inferior (Bottom Navigation).

### 3.3 Flujo de Trabajo Git y Contribución
- **Prohibido trabajar directo en `main` o `dev`:** Los commits directos están prohibidos en estas dos ramas.
- **Ramas individuales y PRs a `dev`:** Todo desarrollador o agente debe trabajar en su propia rama (ej. `dev-luis` o `feat/<id-historia>`) y subir sus cambios mediante Pull Request con destino estricto a la rama `dev`.
- Consultar la guía completa de contribución en [`CONTRIBUTING.md`](CONTRIBUTING.md).

### 3.4 Flujo de Trabajo ODD (Organic Driven Development)
1. **Planificar:** Desglosar tareas en unidades atómicas y registrarlas en `odd/tasks/<feature>.md` y la memoria de Engram.
2. **Test-First cuando aplique:** Crear pruebas unitarias o de integración automatizadas antes de dar por cerrada una funcionalidad.
3. **Commits en Unidades de Trabajo:** Commits descriptivos bajo la convención *Conventional Commits* (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`).
