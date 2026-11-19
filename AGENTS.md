# SkillMatch — Instrucciones Maestras y Gobernanza de Agentes (AGENTS.md)

Este documento es el **contrato maestro de desarrollo asistido por Inteligencia Artificial** para el proyecto **SkillMatch**. Todo agente autónomo, subagente o modelo que intervenga en este repositorio debe respetar de forma irrestricta los principios, reglas y arquitecturas aquí plasmadas.

---

## 1. Principios Fundamentales del Sistema

### 1.1 Política de IA para evaluación de respuestas
- **Proveedores permitidos:** Gemini y la API de OpenAI pueden evaluar las respuestas del usuario y generar feedback según la pregunta, respuesta de referencia y rúbrica definidas por el administrador. El proveedor y modelo se seleccionan mediante configuración del backend en `.env`.
- **Privacidad y consentimiento:** Por defecto se envía únicamente el texto necesario para la corrección, sin nombres, documentos, rostros ni otros identificadores. Enviar audio o video a un proveedor externo requiere autorización y consentimiento específicos; no se deduce de permitir corregir texto.
- **Secretos:** Las claves se mantienen exclusivamente en el backend, tipadas con `SecretStr`, nunca en el frontend, repositorio o logs. Toda nueva variable debe documentarse y plantillarse según la sección 3.1.
- **Corrección controlada:** El backend valida las salidas del proveedor, conserva la versión de la rúbrica y registra qué proveedor/modelo corrigió cada evaluación. Un error o respuesta inválida del proveedor no equivale a una respuesta incorrecta del usuario ni autoriza una aprobación simulada.
- **Procesamiento especializado local:** Se mantienen los componentes propios/open-source para AST y sandbox de programación, análisis musical con `librosa`/`PyTorch` y visión/pose con `OpenCV`/`PyTorch`. Esta autorización no cambia autenticación, biometría, supervisión ni consumo de intentos.
- **Banco de preguntas:** Las preguntas y rúbricas se cargan y revisan en el banco administrativo; permitir un corrector externo no autoriza generar preguntas improvisadas durante el examen.
- **Decisión vigente:** Esta política reemplaza la prohibición anterior de APIs LLM externas para la corrección de respuestas. Las referencias históricas a esa prohibición deben alinearse al implementar el flujo; no deben volver a bloquear esta autorización.

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
- `MEMBER`: Miembro de la comunidad (aprendiz e instructor). Autenticación **exclusiva** vía **Google** (identidad verificada, sin GitHub ni WhatsApp/OTP). Sin contraseñas locales ni recuperación de contraseña.
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
- **Gobernanza de Variables de Entorno y Secretos (MANDATORIO):**
  - Todo dato sensible debe tiparse obligatoriamente con `SecretStr` en `Settings` (`app/core/config.py`).
  - Cada vez que un agente o desarrollador introduzca una nueva variable de entorno en el sistema, **es obligatorio actualizar inmediatamente la documentación**:
    1. Agregar la variable con su valor por defecto o plantilla en `backend/env.template`.
    2. Actualizar el bloque de variables de entorno en el `backend/README.md`.
    3. Nunca dejar variables de entorno "fantasma" que no estén documentadas ni plantilladas.

### 3.2 Estándares de Frontend (React / TypeScript / Zustand / Tailwind)
- **Tipado estricto:** TypeScript estricto sin uso de `any`.
- **Uso Obligatorio de Componentes Shadcn (`frontend/src/components/ui/`):** Está terminantemente prohibido reinventar la rueda o maquetar componentes con elementos HTML nativos (`<button>`, `<select>`, `<input>`, checkboxes nativos o tabs caseros) cuando ya existen componentes oficiales y bien diseñados en `frontend/src/components/ui/` (ej. `Button`, `Input`, `Select`, `Dialog`, `Card`, `Badge`, `Tabs`, `Switch`, `Table`, `Label`, `Textarea`, etc.). Todo agente o desarrollador debe importar y reutilizar sí o sí estos componentes para garantizar la identidad visual del preset **Mist**, consistencia de accesibilidad y evitar pérdida de tiempo.
- **Estética y Design System:** Shadcn/ui con preset **Mist** (paleta de colores fríos, verde esmeralda institucional, tipografía Inter).
- **Gestión de Estado:** Tiendas atómicas y modulares con **Zustand**. No inflar estados globales innecesarios.
- **Responsividad:** 100% responsive en móvil, tablet y desktop; en móvil la navegación principal reside en la barra inferior (Bottom Navigation).

### 3.3 Flujo de Trabajo Git y Contribución
- **Prohibido trabajar directo en `main` o `dev`:** Los commits directos están prohibidos en estas dos ramas.
- **Ramas individuales y PRs a `dev`:** Todo desarrollador o agente debe trabajar en su propia rama (ej. `dev-luis` o `feat/<id-historia>`) y subir sus cambios mediante Pull Request con destino estricto a la rama `dev`.
- **Commits en Inglés Obligatorio:** Todos los mensajes de commit deben estar redactados estrictamente en **inglés** bajo Conventional Commits (`feat:`, `fix:`, `chore:`, etc.), comenzando con verbo en imperativo (`add`, `fix`, `update`), sin punto final y con un máximo de 50 caracteres en el título.
- Consultar la guía completa de contribución en [`CONTRIBUTING.md`](CONTRIBUTING.md).

### 3.4 Flujo de Trabajo ODD (Organic Driven Development)
1. **Planificar:** Desglosar tareas en unidades atómicas y registrarlas en `odd/tasks/<feature>.md` y la memoria de Engram.
2. **Test-First cuando aplique:** Crear pruebas unitarias o de integración automatizadas antes de dar por cerrada una funcionalidad.
3. **Commits en Unidades de Trabajo:** Commits descriptivos bajo la convención *Conventional Commits* (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`).
