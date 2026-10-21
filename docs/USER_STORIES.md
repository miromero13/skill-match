# SkillMatch — Backlog de Historias de Usuario (Jira Ready)

*Planificación ágil por Sprints (Sprint 0 al Sprint 4) con cobertura integral de backend y frontend por historia, Landing Page pública, autenticación social/OTP para miembros (Google, WhatsApp, GitHub), login local exclusivo para Administradores, economía de puntos con recargas, propinas y retiros en dinero (Cashout), gestión de quejas con compensación, política de seguridad 404 Not Found y estado inicial **Por hacer**.*

---

## 1. Inventario de Épicas (Jira Epics)

| Clave Épica | Nombre de la Épica | Descripción |
|---|---|---|
| **EPIC-01** | Preparación, Documentación y Diseño del Sistema | Redacción técnica formal (Capítulos 1 al 3, anexos y bibliografía), backlog en Jira, prototipo Figma y Landing Page pública. |
| **EPIC-02** | Inicialización y Estructura del Proyecto | Scaffolding modular del Backend (FastAPI, PostgreSQL, Swagger y migraciones Alembic) y Frontend/Mobile (React, Shadcn Mist, Zustand y Capacitor). |
| **EPIC-03** | Miembros, Proveedores de Autenticación y Administración | Registro rápido con Google, WhatsApp y GitHub, login de administrador por clave, gestión de administradores y sesión JWT. |
| **EPIC-04** | Catálogo y Habilidades | Administración de categorías, oferta y demanda de habilidades, niveles declarados y portafolio de evidencias. |
| **EPIC-05** | Datasets e Ingesta de Datos para IA | Herramienta de captura web/móvil y consola de anotación de muestras gestionada por administradores para entrenar modelos propios. |
| **EPIC-06** | Búsqueda y Matching | Búsqueda con filtros, motor de compatibilidad bilateral recíproca, cálculo de afinidad y tarjetas de coincidencia. |
| **EPIC-07** | Notificaciones y Tiempo Real | Conexión WebSocket para eventos inmediatos, historial de avisos y preferencias del usuario. |
| **EPIC-08** | Evaluación de Código y Sandbox | Editor en navegador, ejecutor en sandbox Docker aislado, análisis por AST de Python y defensa por plantillas. |
| **EPIC-09** | Supervisión y Prevención de Fraude | Consentimiento biométrico en evaluación, prueba de vida (*liveness*), bloqueo de portapapeles y auditoría administrativa. |
| **EPIC-10** | Modelos de IA para Música y Deportes | Procesamiento de audio espectral (librosa) y visión computacional con tracking de pose y balón (OpenCV/PyTorch). |
| **EPIC-11** | Sesiones de Intercambio, Reputación y Pasaporte | Agendamiento (cupos gratuitos y cancelaciones), confirmación recíproca, calificaciones mutuas, propinas y Pasaporte QR. |
| **EPIC-12** | Economía de Puntos, Billetera y Resolución de Quejas | Recarga de puntos, pago de clases no recíprocas, retiro en dinero real (Cashout) y resolución de quejas con compensación por Admin. |

---

## 2. Definición Canónica de Roles y Modelo de Accesos

El sistema opera bajo un modelo estricto de **dos roles únicos** tipados como Enum en ambos extremos:

### 2.1 Backend (Python / FastAPI)
```python
from enum import Enum

class UserRole(str, Enum):
    MEMBER = "MEMBER"  # Miembro de la comunidad (aprendiz e instructor de habilidades)
    ADMIN = "ADMIN"    # Administrador de la plataforma (gestor de catálogo, datasets, administradores y auditoría)
```

### 2.2 Frontend (TypeScript / React)
```typescript
export enum UserRole {
  MEMBER = "MEMBER",
  ADMIN = "ADMIN"
}
```

### 2.3 Reglas de Autenticación, JWT y Gobernanza de Roles
1. **Miembros de la Comunidad (`MEMBER`):**
   - Se registran e inician sesión **exclusivamente mediante proveedores externos**: **Google**, **WhatsApp** y **GitHub**.
   - No disponen de contraseña en la plataforma, por lo que **no existe flujo de recuperación de contraseña** para ellos.
   - El registro es inmediato (*onboarding rápido*): no se solicita consentimiento biométrico en el registro inicial.
2. **Administradores (`ADMIN`):**
   - El sistema cuenta con un administrador inicial configurado por seed seguro en base de datos.
   - Los administradores inician sesión **exclusivamente con correo electrónico y contraseña**.
   - No disponen de recuperación de clave por correo electrónico (la seguridad administrativa se gestiona internamente).
   - **Creación de nuevos administradores:** Un usuario `ADMIN` autenticado puede dar de alta nuevos administradores asignando correo, nombre y contraseña inicial.
   - **Sin asignación de roles a miembros comunes:** Los miembros no pueden ser promovidos ni cambiados de rol; los administradores son creados directamente como cuentas administrativas dedicadas.
3. **Contrato Dinámico de Seguridad en Tokens JWT:**
   - Todo token de acceso emitido codifica en su payload el claim dinámico `"role": user.role.value` (`"MEMBER"` si quien autentica es miembro, o `"ADMIN"` si es administrador):
     ```json
     {
       "sub": "user_uuid_12345",
       "email": "usuario@skillmatch.com",
       "role": "MEMBER",
       "exp": 1740000000
     }
     ```
   - Al recibir una solicitud, las dependencias de FastAPI (`require_role`) inspeccionan este claim del token JWT y autorizan el acceso únicamente si el rol autenticado coincide con el rol exigido por la ruta; de lo contrario, deniegan la operación.
4. **Política de Seguridad por Ofuscación (Página 404 Not Found):**
   - Si un miembro (`MEMBER`) o visitante no autenticado intenta acceder a una ruta de administración en el navegador (ej. `/admin/...`), el frontend **no muestra un error de "Acceso Prohibido" ni "403 Forbidden"**, sino que renderiza directamente la página **404 Not Found (Página no encontrada)**. El miembro no tiene por qué saber que esa pantalla o funcionalidad existe en el sistema.
   - En el backend, cualquier petición a rutas administrativas no autorizadas responde con `statuscode: 404` y `message: "Recurso no encontrado"`.
   - En el **Sidebar**, los enlaces administrativos solo se renderizan si el rol autenticado en el store de Zustand es estrictamente `UserRole.ADMIN`.

---

## 3. Formato Estándar de Respuesta de la API

Todas las respuestas emitidas por el backend deben seguir estrictamente el siguiente esquema JSON unificado:

```json
{
  "statuscode": 200,
  "message": "Operación completada exitosamente",
  "data": { },
  "count": 0
}
```

- `statuscode` (obligatorio): Número entero correspondiente al código de estado HTTP (ej. 200, 201, 400, 401, 403, 404, 500).
- `message` (obligatorio): Mensaje claro y descriptivo del resultado o del error ocurrido. El frontend **debe consumir y mostrar textualmente este mensaje** en sus toasts, alertas y diálogos.
- `data` (obligatorio): Objeto `{ }` o lista `[ ]` con el resultado de la operación (o `null` en caso de error o acciones sin retorno de entidad).
- `count` (opcional): Cantidad total de registros devueltos; se incluye de manera opcional exclusivamente cuando la respuesta sea un listado con paginación.

---

## 4. Resumen de Capacidad por Sprint

| Sprint | Enfoque Principal | Total HUs | Puntos de Historia (SP) |
|:---:|---|:---:|:---:|
| **Sprint 0** | Documentación, backlog, prototipo, inicialización backend/frontend, Landing Page y autenticación social/admin. | 11 | 55 SP |
| **Sprint 1** | Catálogo de habilidades, gestión de oferta/demanda, perfiles y captura/anotación de datasets por Admin. | 8 | 39 SP |
| **Sprint 2** | Motor de búsqueda, matching bilateral, cálculo de score y notificaciones en tiempo real vía WebSockets. | 7 | 34 SP |
| **Sprint 3** | Consentimiento biométrico, evaluador de código (sandbox + AST), prueba teórica y anti-fraude. | 8 | 39 SP |
| **Sprint 4** | Modelos de IA (música/fútbol), sesiones, valoraciones con propinas, Pasaporte QR, Billetera y Quejas. | 9 | 52 SP |
| **Total** | | **43 HUs** | **219 SP** |

---

## 5. Historias de Usuario Detalladas

---

### SPRINT 0: Preparación, Inicialización, Landing Page y Gestión de Accesos

#### HU-01: Documentación técnica inicial del sistema (Capítulos 1 al 3, Anexos y Bibliografía)
- **Épica:** `EPIC-01: Preparación, Documentación y Diseño del Sistema`
- **Actor Principal:** Equipo de Ingeniería / Stakeholders
- **Roles Permitidos:** N/A (Documentación técnica de proyecto)
- **Sprint:** Sprint 0
- **Estado:** Por hacer
- **Puntos de Historia:** 5
- **Prioridad:** Alta
- **Trazabilidad:** Marco Teórico, Herramientas y Requerimientos
- **Descripción:**
  > **Como** equipo del proyecto,  
  > **quiero** estructurar y redactar la documentación formal del sistema cubriendo desde el Capítulo 1 hasta el Capítulo 3, con sus respectivos Anexos y Bibliografía,  
  > **para** contar con el marco conceptual, metodológico y de ingeniería formal del producto.
- **Vistas Usadas o a Realizar:**
  - **Web Desktop:** Página 0: `Design System & Guia` + Documentación Académica Formal (Capítulos 1 al 3)
  - **Mobile Responsive:** Página 0: `Design System & Guia` (Diseño de Tokens y Tipografía)
  - **Alcance Visual:** N/A — Documentación técnica académica y guía formal de tokens de diseño
- **Criterios de Aceptación:**
  - [ ] **Capítulo 1:** Marco Teórico desarrollado (*Skill Swapping*, aprendizaje colaborativo, evaluación de competencias en programación, música y fútbol, conceptos de IA/ML/CV y marco ágil Scrum con roles, artefactos y ceremonias detalladas).
  - [ ] **Capítulo 2:** Herramientas tecnológicas justificadas (Python, TypeScript, FastAPI, React, Capacitor, PostgreSQL, Modelo C4 en 4 niveles, Enterprise Architect, VPS Coolify, Jira Software y Git/GitHub).
  - [ ] **Capítulo 3:** Requerimientos del sistema (propósito, ámbito, definiciones y acrónimos, funciones del producto, catálogo de paquetes de casos de uso y especificación técnica de requisitos).
  - [ ] **Anexos y Bibliografía:** Estructurados formalmente bajo normas académicas con fuentes primarias y secundarias citadas.
  - [ ] Redacción coherente con los lineamientos de diseño e identidad visual del sistema.

---

#### HU-02: Historias de Usuario y planificación en Jira
- **Épica:** `EPIC-01: Preparación, Documentación y Diseño del Sistema`
- **Actor Principal:** Scrum Master / Equipo de Desarrollo
- **Roles Permitidos:** N/A (Gestión ágil)
- **Sprint:** Sprint 0
- **Estado:** Por hacer
- **Puntos de Historia:** 3
- **Prioridad:** Alta
- **Trazabilidad:** Metodología Scrum y Gobernanza
- **Descripción:**
  > **Como** equipo de gestión ágil,  
  > **quiero** crear y configurar todas las Historias de Usuario en Jira Software con sus épicas, prioridades y criterios de aceptación, distribuyéndolas en los sprints planificados,  
  > **para** coordinar el avance del proyecto y dar visibilidad al desarrollo.
- **Vistas Usadas o a Realizar:**
  - **Web Desktop:** N/A — Configuración y parametrización ágil del backlog en Jira Software
  - **Mobile Responsive:** N/A — Configuración y parametrización ágil del backlog en Jira Software
  - **Alcance Visual:** N/A — Gobernanza de proyecto y tableros Scrum
- **Criterios de Aceptación:**
  - [x] Tablero Scrum configurado en Jira con los estados del flujo de trabajo (*To Do*, *In Progress*, *Review/QA*, *Done*).
  - [x] Épicas creadas y vinculadas a todas las Historias de Usuario.
  - [x] Carga completa de descripciones en formato estándar (*Como / Quiero / Para*), criterios de aceptación duales, prioridades (A/M/B) y puntos de historia en escala Fibonacci.
  - [x] Distribución de las historias en los 5 sprints (Sprint 0 al 4) garantizando carga balanceada.
  - [x] Configuración de tableros de seguimiento, filtros por componente y reportes de velocidad/burndown.

---

#### HU-03: Inicialización y Arquitectura Base del Backend
- **Épica:** `EPIC-02: Inicialización y Estructura del Proyecto`
- **Actor Principal:** Desarrollador Backend
- **Roles Permitidos:** N/A (Infraestructura y scaffolding base)
- **Sprint:** Sprint 0
- **Estado:** Por hacer
- **Puntos de Historia:** 8
- **Prioridad:** Alta
- **Trazabilidad:** SIBC Software, Cap. 2.2, 2.3
- **Descripción:**
  > **Como** desarrollador backend,  
  > **quiero** inicializar el proyecto base con FastAPI y PostgreSQL, asegurando una arquitectura modular, formato de respuesta unificado (`statuscode`, `message`, `data`, y opcional `count` en listados paginados) usando interfaces/schemas, migraciones con Alembic y documentación interactiva con Swagger,  
  > **para** disponer de una API base sólida, ordenada y autodocumentada (sin usuarios, roles ni permisos aún).
- **Vistas Usadas o a Realizar:**
  - **Web Desktop:** N/A — Scaffolding de FastAPI, PostgreSQL, Alembic y Swagger UI (`/docs`)
  - **Mobile Responsive:** N/A — Scaffolding de FastAPI, PostgreSQL, Alembic y Swagger UI (`/docs`)
  - **Alcance Visual:** N/A — Infraestructura de Backend y contratos de API
- **Criterios de Aceptación:**
  - **Backend:**
    - [ ] Arquitectura modular y limpia que facilite la escalabilidad y mantenimiento del código.
    - [ ] Formato de respuesta unificado en todas las peticiones con el schema estándar (`statuscode`, `message`, `data`, y `count` opcional en listados).
    - [ ] Manejo centralizado de excepciones que capture errores HTTP, de validación (422) y fallos internos (500) devolviendo el sobre estándar con su respectivo `statuscode` y `message`.
    - [ ] Conexión asíncrona a PostgreSQL (`asyncpg` + SQLAlchemy 2.0) y sistema de migraciones configurado con Alembic (comandos de `upgrade head` y `downgrade` plenamente operativos).
    - [ ] Registro completo y documentación interactiva en **Swagger UI** (`/docs`) y especificación OpenAPI activa y funcional.
    - [ ] Middlewares de seguridad, compresión GZip y políticas de CORS parametrizadas por variables de entorno en `.env`.
    - [ ] Configuración de `docker-compose.yml` para levantar PostgreSQL de forma reproducible con volúmenes persistentes.
    - [ ] Documentación en `backend/README.md` con contexto, arquitectura e instrucciones claras para ejecutar el proyecto tanto localmente con entorno virtual como con Docker.

---

#### HU-04: Inicialización del Frontend y Configuración Móvil con Capacitor
- **Épica:** `EPIC-02: Inicialización y Estructura del Proyecto`
- **Actor Principal:** Desarrollador Frontend
- **Roles Permitidos:** N/A (Infraestructura y scaffolding base)
- **Sprint:** Sprint 0
- **Estado:** Listo
- **Puntos de Historia:** 8
- **Prioridad:** Alta
- **Trazabilidad:** SIBC Software, Cap. 2.1, 2.2
- **Descripción:**
  > **Como** desarrollador frontend,  
  > **quiero** inicializar el proyecto con React y TypeScript de forma modular, con rutas configuradas, cliente HTTP tipado con interfaces, gestor de estado global con Zustand, diseño con Shadcn/ui (preset Mist, font Inter) y configuración de Capacitor para móvil,  
  > **para** tener la base de la aplicación web y móvil lista para el desarrollo (sin usuarios, roles ni permisos aún).
- **Vistas Usadas o a Realizar:**
  - **Web Desktop:** Página 2: Todas las vistas de Web Desktop (`01` a `30`)
  - **Mobile Responsive:** Página 1: Todas las vistas de Mobile Responsive (`01` a `32`)
  - **Alcance Visual:** Vista Completa — Shell base transversal y paridad de navegación 1:1 (Navbar, Sidebar, Bottom Bar, StatusBar)
- **Criterios de Aceptación:**
  - **Frontend:**
    - [x] Estructura modular del proyecto que organice componentes, vistas y servicios de forma limpia y mantenible.
    - [x] Configuración del sistema de rutas (React Router) con layout público, layout de plataforma, layout de examen en pantalla completa y **pantalla 404 Not Found dedicada**.
    - [x] Integración de **Zustand** para la gestión centralizada del estado global de la aplicación.
    - [x] Capa de comunicación con el Backend preparada con cliente HTTP tipado con interfaces, interceptores y extracción automática del `message` para la retroalimentación de usuario.
    - [x] Integración de Shadcn/ui siguiendo el preset oficial ([https://ui.shadcn.com/create?preset=b7BFgTjg8](https://ui.shadcn.com/create?preset=b7BFgTjg8)), paleta de colores Mist y tipografía Inter.
    - [x] Configuración completa de Capacitor con `@capacitor/core` y `@capacitor/cli` (`appId: com.skillmatch.app`), vinculando plataformas `@capacitor/android` e `@capacitor/ios`.
    - [x] Permisos iniciales configurados en `AndroidManifest.xml` e `Info.plist` para acceso a hardware de cámara y micrófono.
    - [x] Scripts en `package.json` listos para build web y sincronización nativa (`cap sync`, `cap open android`).
    - [x] Diseño y estructura base 100% responsive comprobado en mobile, tablet y desktop.
    - [x] Documentación en `frontend/README.md` con contexto, arquitectura e instrucciones para ejecutar el proyecto en web y en móvil con Capacitor.

---

#### HU-05: Prototipo completo del sistema en alta fidelidad
- **Épica:** `EPIC-01: Preparación, Documentación y Diseño del Sistema`
- **Actor Principal:** Diseñador UI/UX
- **Roles Permitidos:** N/A (Diseño de interfaces)
- **Sprint:** Sprint 0
- **Estado:** Por hacer
- **Puntos de Historia:** 8
- **Prioridad:** Alta
- **Trazabilidad:** UI/UX, Requisitos del producto
- **Descripción:**
  > **Como** diseñador de experiencia de usuario,  
  > **quiero** diseñar el prototipo interactivo completo de alta fidelidad que cubra todas las pantallas y flujos de las Historias de Usuario,  
  > **para** que sirva de guía visual indiscutible para el desarrollo y validación funcional.
- **Vistas Usadas o a Realizar:**
  - **Web Desktop:** Página 2: Lienzo completo de Web Desktop (Vistas `01` a `30`)
  - **Mobile Responsive:** Página 1: Lienzo completo de Mobile Responsive (Vistas `01` a `32`)
  - **Alcance Visual:** Vista Completa — Prototipo interactivo integral en OpenPencil (`skillmatch-prototype.op`)
- **Criterios de Aceptación:**
  - [x] Prototipo diseñado en Figma siguiendo como referencia directa el preset de Shadcn/ui: [https://ui.shadcn.com/create?preset=b7BFgTjg8](https://ui.shadcn.com/create?preset=b7BFgTjg8).
  - [x] Aplicación estricta de la paleta **Mist**, bordes/radios del preset y tipografía **Inter**.
  - [x] Diseño 100% responsive adaptable tanto a pantallas de escritorio (Web) como a dispositivos móviles (Capacitor).
  - [x] Cobertura completa de todos los flujos clave:
    1. Landing Page de presentación y botones de acceso rápido (Google, WhatsApp, GitHub) y acceso login de Administrador.
    2. Perfil de miembro y catálogo de habilidades (enseñar / aprender).
    3. Flujo de validación: modal de consentimiento biométrico previo, verificación de entorno, liveness, editor de código sandbox con tests, reto con cámara y reporte de resultados.
    4. Búsqueda con filtros facetados, Match Cards interactivas y chat de coincidencia.
    5. Agendamiento de sesiones con control de cupos gratuitos de 1h, cancelación con motivo, confirmación post-encuentro, propinas en puntos y valoraciones mutuas.
    6. Billetera de puntos (recargas y solicitud de cashout), centro de quejas y Pasaporte de Habilidades público con código QR.

---

#### HU-06: Landing Page pública y presentación de la plataforma
- **Épica:** `EPIC-01: Preparación, Documentación y Diseño del Sistema`
- **Actor Principal:** Visitante / Público General
- **Roles Permitidos:** Público (Sin autenticación requerida)
- **Sprint:** Sprint 0
- **Estado:** Por hacer
- **Puntos de Historia:** 5
- **Prioridad:** Alta
- **Trazabilidad:** Requisitos del producto, Presentación
- **Descripción:**
  > **Como** visitante que llega a SkillMatch,  
  > **quiero** explorar una página de aterrizaje interactiva, moderna y clara,  
  > **para** comprender la propuesta de valor del intercambio de habilidades con validación por IA y registrarme o iniciar sesión en un clic.
- **Vistas Usadas o a Realizar:**
  - **Web Desktop:** `30 - Landing Page Pública (Presentación Institucional)`
  - **Mobile Responsive:** `32 - Mobile Landing Page Institucional`
  - **Alcance Visual:** Vista Completa — Portada pública de 2800px (Navbar pública, Hero, Cómo Funciona en 3 pasos, Demos de las 3 áreas de IA, Métricas en vivo y Footer)
- **Criterios de Aceptación:**
  - **Backend:**
    - [ ] Endpoints públicos documentados en Swagger UI (`/docs`):
      - `GET /api/platform/stats`: Estadísticas públicas consolidadas de la plataforma (total de habilidades activas en catálogo, intercambios exitosos completados y miembros registrados) respondiendo en el sobre estándar `APIResponse`.
  - **Frontend:**
    - [ ] Ruta `/` pública implementada con el preset Shadcn/ui Mist y tipografía Inter.
    - [ ] **Sección Hero:** Encabezado con propuesta de valor de alto impacto (*Skill Swapping colaborativo con validación objetiva por Inteligencia Artificial*) y botones de llamada a la acción (*Call-to-Action*) directos para iniciar con Google, WhatsApp o GitHub.
    - [ ] **Sección Cómo Funciona:** Flujo explicativo interactivo en 3 pasos (1. Registrá tus habilidades a enseñar y aprender; 2. Valida tu nivel con IA propia; 3. Hacé match recíproco y coordiná sesiones de clase).
    - [ ] **Sección Áreas de Validación IA:** Demostración visual de las tres verticales (Programación con editor y sandbox, Instrumentos con análisis de audio y Fútbol con visión artificial).
    - [ ] **Sección Estadísticas en Vivo:** Consumo dinámico de `/api/platform/stats` con datos hidratados mediante store de **Zustand**.
    - [ ] **Navbar y Footer:** Barra superior fija con enlaces a catálogo público, botón de acceso rápido y pie de página con enlaces institucionales.
    - [ ] Diseño 100% responsive comprobado en mobile, tablet y desktop.

---

#### HU-07: Registro rápido y autenticación de miembros con Google, WhatsApp y GitHub
- **Épica:** `EPIC-03: Miembros, Proveedores de Autenticación y Administración`
- **Actor Principal:** Visitante / Nuevo Miembro de la Comunidad
- **Roles Permitidos:** Público (Sin autenticación previa)
- **Sprint:** Sprint 0
- **Estado:** Por hacer
- **Puntos de Historia:** 5
- **Prioridad:** Alta
- **Trazabilidad:** `RF-USR-01`, `RF-USR-02`
- **Descripción:**
  > **Como** nuevo miembro o miembro existente de la comunidad,  
  > **quiero** registrarme e iniciar sesión de forma ágil usando mi cuenta de Google, GitHub o verificación de WhatsApp sin contraseñas,  
  > **para** acceder de inmediato a la plataforma sin trámites engorrosos ni necesidad de recordar claves.
- **Vistas Usadas o a Realizar:**
  - **Web Desktop:** `28 - Registro & Autenticación de Miembros (Social & OTP)`
  - **Mobile Responsive:** `30 - Mobile Registro & Auth Miembros`
  - **Alcance Visual:** Vista Completa — Auth Card con botones de acceso Google y GitHub, selector de prefijo de país y slots de 6 dígitos para código OTP de WhatsApp
- **Criterios de Aceptación:**
  - **Backend:**
    - [ ] Endpoints documentados en Swagger UI (`/docs`):
      - `POST /api/auth/oauth/google`: Intercambia token OAuth de Google por sesión JWT.
      - `POST /api/auth/oauth/github`: Intercambia código OAuth de GitHub por sesión JWT.
      - `POST /api/auth/otp/whatsapp/request`: Envía código de un solo uso por WhatsApp.
      - `POST /api/auth/otp/whatsapp/verify`: Valida código OTP e inicia/crea sesión de miembro.
    - [ ] Modelo `User` con campos de proveedor: `provider` (google, github, whatsapp), `provider_user_id`, `email`, `phone_number`, `full_name`, `avatar_url`, `role` (`UserRole.MEMBER`), `is_active = true`.
    - [ ] Creación de billetera automática (`Wallet`) con saldo inicial de 0 puntos asociada al nuevo miembro.
    - [ ] Provisionamiento automático (*Just-In-Time*): si el usuario no existe, se crea automáticamente en estado verificado y activo con rol `UserRole.MEMBER`.
    - [ ] Sin gestión de contraseña para este tipo de usuarios (`password_hash = null`).
    - [ ] Emisión de Access Token y Refresh Token con el claim `"role": "MEMBER"`.
  - **Frontend:**
    - [ ] Pantalla de Login / Registro rápido con botones de acción social estilizados con Shadcn/ui (Google, WhatsApp, GitHub).
    - [ ] Flujo interactivo de ingreso de número telefónico y diálogo de código OTP para WhatsApp.
    - [ ] Gestión del estado de autenticación y tokens en store de **Zustand**.
    - [ ] Despliegue de mensajes informativos y de error con el `message` del backend en toasts.
    - [ ] Interfaz 100% responsive en mobile, tablet y desktop.

---

#### HU-08: Autenticación exclusiva para Administradores con Correo y Contraseña
- **Épica:** `EPIC-03: Miembros, Proveedores de Autenticación y Administración`
- **Actor Principal:** Administrador de la Plataforma
- **Roles Permitidos:** Público para login de administración
- **Sprint:** Sprint 0
- **Estado:** Por hacer
- **Puntos de Historia:** 5
- **Prioridad:** Alta
- **Trazabilidad:** `RF-USR-04`, `RF-USR-10`
- **Descripción:**
  > **Como** administrador de SkillMatch,  
  > **quiero** iniciar sesión en un acceso administrativo seguro mediante mi correo electrónico institucional y contraseña,  
  > **para** acceder al panel de control de la plataforma (sin recuperación de contraseña por correo).
- **Vistas Usadas o a Realizar:**
  - **Web Desktop:** `29 - Login Exclusivo de Administradores (/admin/login)`
  - **Mobile Responsive:** `31 - Mobile Login Administradores`
  - **Alcance Visual:** Vista Completa — Pantalla sobria `#0F1416` con formulario de correo institucional, contraseña cifrada y aviso de seguridad 404 Not Found
- **Criterios de Aceptación:**
  - **Backend:**
    - [ ] Endpoint documentado en Swagger UI (`/docs`):
      - `POST /api/admin/auth/login`: Autentica credenciales administrativas (`email` y `password`).
    - [ ] Validación estricta de que el usuario posea rol `UserRole.ADMIN` y cuenta activa (`is_active = true`).
    - [ ] Verificación de contraseña hasheada con Argon2/Bcrypt.
    - [ ] Emisión de par de tokens JWT conteniendo el claim `"role": "ADMIN"`.
    - [ ] Sin flujo de recuperación de clave por correo para cuentas administrativas.
    - [ ] Bloqueo preventivo tras 5 intentos fallidos consecutivos de acceso.
  - **Frontend:**
    - [ ] Vista `/admin/login` independiente con formulario de correo y contraseña (diseño discreto Shadcn Mist).
    - [ ] Almacenamiento seguro del token y del rol `UserRole.ADMIN` en el store de **Zustand**.
    - [ ] Redirección automática al panel de administración `/admin/dashboard` tras éxito.
    - [ ] Avisos de error visuales mostrando textualmente el `message` recibido del backend.
    - [ ] Diseño 100% responsive en mobile, tablet y desktop.

---

#### HU-09: Gestión de sesión JWT unificada y persistencia
- **Épica:** `EPIC-03: Miembros, Proveedores de Autenticación y Administración`
- **Actor Principal:** Usuario Autenticado (`MEMBER` o `ADMIN`)
- **Roles Permitidos:** `UserRole.MEMBER`, `UserRole.ADMIN`
- **Sprint:** Sprint 0
- **Estado:** Por hacer
- **Puntos de Historia:** 5
- **Prioridad:** Alta
- **Trazabilidad:** `RF-USR-04`
- **Descripción:**
  > **Como** miembro o administrador con sesión iniciada,  
  > **quiero** mantener mi sesión persistente y poder cerrarla cuando lo desee,  
  > **para** navegar de forma continua y segura tanto en navegador web como en aplicación móvil.
- **Vistas Usadas o a Realizar:**
  - **Web Desktop:** `01 - Shell Maestro Web` (y cabecera de todas las vistas autenticadas)
  - **Mobile Responsive:** `01 - Mobile Feed (Home)` (y header de todas las vistas autenticadas)
  - **Alcance Visual:** Solo una parte de esa vista — Topbar / Mobile Header: Avatar de usuario logueado, saldo de puntos (150 SP), botón de logout y persistencia Zustand
- **Criterios de Aceptación:**
  - **Backend:**
    - [ ] Endpoints documentados en Swagger UI (`/docs`):
      - `POST /api/auth/refresh`: Renueva el token de acceso rotando el Refresh Token y preservando el claim `"role"` (ya sea `MEMBER` o `ADMIN`).
      - `POST /api/auth/logout`: Revoca el token de sesión.
      - `GET /api/auth/me`: Retorna la identidad, perfil y rol del usuario autenticado actual.
    - [ ] Dependencia de FastAPI `get_current_user` que valida vigencia temporal, algoritmo y firma del JWT.
  - **Frontend:**
    - [ ] Store de **Zustand** que administra el ciclo de vida de la sesión, claims de rol y usuario actual.
    - [ ] Persistencia segura (localStorage en web y Preferences cifradas en Capacitor móvil).
    - [ ] Interceptor Axios que refresca el token automáticamente ante respuestas `401 Unauthorized`.
    - [ ] Redirección al login correspondiente y limpieza completa de estado ante cierre de sesión.
    - [ ] Diseño 100% responsive en mobile, tablet y desktop.

---

#### HU-10: Creación y gestión de nuevos Administradores por parte del Administrador
- **Épica:** `EPIC-03: Miembros, Proveedores de Autenticación y Administración`
- **Actor Principal:** Administrador de la Plataforma
- **Roles Permitidos:** `UserRole.ADMIN`
- **Sprint:** Sprint 0
- **Estado:** Por hacer
- **Puntos de Historia:** 5
- **Prioridad:** Alta
- **Trazabilidad:** `RF-USR-10`, `RF-USR-15`
- **Descripción:**
  > **Como** administrador de SkillMatch,  
  > **quiero** dar de alta nuevas cuentas de administrador ingresando su correo, nombre y contraseña inicial,  
  > **para** delegar la gestión del sistema a otros miembros del equipo administrativo (sin alterar ni asignar roles a miembros comunes).
- **Vistas Usadas o a Realizar:**
  - **Web Desktop:** `15A - Gestión de Usuarios, Administradores y Control RBAC` y `15B - Modal Alta de Nuevo Administrador & RBAC`
  - **Mobile Responsive:** `17A - Mobile Gestión de Usuarios & RBAC` y `17B - Mobile Modal Alta Nuevo Administrador`
  - **Alcance Visual:** Vista Completa — En 15A/17A tabla y control de administradores; en 15B/17B modal formulario de alta con asignación de rol y privilegios RBAC
- **Criterios de Aceptación:**
  - **Backend:**
    - [ ] Endpoints limpios documentados en Swagger UI (`/docs`) y protegidos:
      - `GET /api/admin`: Listado de cuentas administrativas con `count`.
      - `POST /api/admin`: Crea un nuevo usuario administrador con contraseña hasheada y `role = UserRole.ADMIN`.
      - `PATCH /api/admin/{id}/status`: Suspende o reactiva un administrador.
    - [ ] **Política de seguridad 404:** Si un usuario con rol `MEMBER` o sin token intenta llamar a estos endpoints, el backend responde con `statuscode: 404` y `message: "Recurso no encontrado"`.
  - **Frontend:**
    - [ ] Vista `/admin/administrators` protegida: si el usuario no tiene rol `UserRole.ADMIN`, la guardia de ruta renderiza directamente la página **404 Not Found**.
    - [ ] **Restricción en Sidebar:** El apartado "Equipo Administrador" solo es visible para `UserRole.ADMIN`.
    - [ ] Formulario de alta con validación de contraseña robusta y correo único gestionado en **Zustand**.
    - [ ] Toasts con el `message` del backend.
    - [ ] Diseño 100% responsive en mobile, tablet y desktop.

---

#### HU-11: Consentimiento informado de biometría y periféricos al solicitar validación de habilidad
- **Épica:** `EPIC-09: Supervisión y Prevención de Fraude`
- **Actor Principal:** Miembro de la Comunidad
- **Roles Permitidos:** `UserRole.MEMBER`
- **Sprint:** Sprint 0
- **Estado:** Por hacer
- **Puntos de Historia:** 3
- **Prioridad:** Alta
- **Trazabilidad:** `RF-USR-14`, `RF-FRA-19`
- **Descripción:**
  > **Como** miembro que desea validar una habilidad,  
  > **quiero** revisar y aceptar los términos de uso de cámara, micrófono y procesamiento de biometría justo antes de comenzar mi evaluación,  
  > **para** dar mi consentimiento informado únicamente cuando decido someterme a una prueba supervisada por IA.
- **Vistas Usadas o a Realizar:**
  - **Web Desktop:** `04B - Pre-embarque: Paso 2 (Normas de Integridad)`
  - **Mobile Responsive:** `06B - Mobile Pre-embarque: Paso 2 (Normas)`
  - **Alcance Visual:** Vista Completa — Paso 2 del stepper: términos legales, advertencia de periféricos (cámara/micrófono), aviso de 3 pruebas gratis y checkboxes de consentimiento obligatorio
- **Criterios de Aceptación:**
  - **Backend:**
    - [ ] Endpoint documentado en Swagger UI (`/docs`):
      - `POST /api/evaluations/consent`: Registra la aceptación explícita de biometría y periféricos con timestamp inmutable (`biometric_consent_at`) y versión de política aceptada.
    - [ ] Bloqueo estricto del inicio de cualquier evaluación práctica si no existe consentimiento registrado previamente para el miembro.
    - [ ] Verificación de la regla de evaluación gratuita: valida que el miembro no haya superado el límite de 3 habilidades validadas gratis y que mantenga disponible su único intento gratuito por habilidad.
  - **Frontend:**
    - [ ] Modal informativo previo al examen detallando qué periféricos se utilizarán (cámara, micrófono) y para qué fines (anti-fraude y evaluación).
    - [ ] Indicador visual: *"Validación gratuita restante: X/3 habilidades (Intento 1/1)"*.
    - [ ] Checkboxes explícitos de consentimiento antes de habilitar el botón "Comenzar Evaluación".
    - [ ] Gestión del estado del consentimiento en store de **Zustand**.
    - [ ] Notificaciones con el `message` del backend.
    - [ ] Diseño 100% responsive en mobile, tablet y desktop.

---

### SPRINT 1: Catálogo de Habilidades, Perfiles e Ingesta de Datasets de IA

#### HU-12: Catálogo maestro de habilidades y taxonomía
- **Épica:** `EPIC-04: Catálogo y Habilidades`
- **Actor Principal:** Administrador (Gestión) / Miembros de la Comunidad (Consulta)
- **Roles Permitidos:** 
  - Consulta: Público / `UserRole.MEMBER`, `UserRole.ADMIN`
  - Mutación: `UserRole.ADMIN`
- **Sprint:** Sprint 1
- **Estado:** Por hacer
- **Puntos de Historia:** 5
- **Prioridad:** Alta
- **Trazabilidad:** `RF-HAB-01`
- **Descripción:**
  > **Como** miembro y administrador,  
  > **quiero** consultar y gestionar el catálogo de habilidades organizado por categorías y subcategorías,  
  > **para** estandarizar los conocimientos disponibles en la plataforma evitando duplicados y nombres redundantes.
- **Vistas Usadas o a Realizar:**
  - **Web Desktop:** `16A - Catálogo Maestro de Habilidades & Aprobaciones` y `16B - Modal Crear Nueva Habilidad / Categoría`
  - **Mobile Responsive:** `18A - Mobile Catálogo Maestro de Habilidades` y `18B - Mobile Modal Nueva Habilidad`
  - **Alcance Visual:** Vista Completa — Árbol jerárquico de Categorías y Subcategorías, Escalera de Niveles 1 al 5, panel de sugerencias comunitarias y modal de creación
- **Criterios de Aceptación:**
  - **Backend:**
    - [ ] Modelos relacionales `Category` y `Skill` con claves foráneas, slugs y migración Alembic.
    - [ ] Restricción de unicidad: `name` y `slug` únicos por categoría normalizados a minúsculas.
    - [ ] Endpoints documentados en Swagger UI (`/docs`):
      - `GET /api/skills`: Consulta del catálogo público con filtros por categoría y campo `count`.
      - `GET /api/skills/{id}`: Detalle de habilidad puntual.
      - `POST /api/admin/skills`: Creación de nueva habilidad (requiere `UserRole.ADMIN`).
      - `PUT /api/admin/skills/{id}`: Actualización integral (requiere `UserRole.ADMIN`).
      - `PATCH /api/admin/skills/{id}/status`: Activación/desactivación lógica (requiere `UserRole.ADMIN`).
      - `DELETE /api/admin/skills/{id}`: Baja lógica protegida, rechazada si hay miembros vinculados (requiere `UserRole.ADMIN`).
    - [ ] **Política 404 en Backend:** Endpoints administrativos devuelven `statuscode: 404` si un miembro común intenta llamarlos.
  - **Frontend:**
    - [ ] Store de catálogo gestionado con **Zustand** (búsqueda, caché local y filtros).
    - [ ] Navegador de catálogo con Command/Combobox de Shadcn/ui y buscador autocompletable.
    - [ ] Panel de administración en `/admin/skills`: si el usuario autenticado tiene rol `MEMBER`, la guardia de ruta renderiza directamente la página **404 Not Found**.
    - [ ] **Restricción en Sidebar:** El enlace "Administrar Catálogo" se muestra exclusivamente para el rol `UserRole.ADMIN`.
    - [ ] Diseño 100% responsive en mobile, tablet y desktop.

---

#### HU-13: Edición de perfil, disponibilidad semanal y modalidad
- **Épica:** `EPIC-03: Miembros, Proveedores de Autenticación y Administración`
- **Actor Principal:** Miembro Autenticado
- **Roles Permitidos:** `UserRole.MEMBER`, `UserRole.ADMIN`
- **Sprint:** Sprint 1
- **Estado:** Por hacer
- **Puntos de Historia:** 5
- **Prioridad:** Alta
- **Trazabilidad:** `RF-USR-07`, `RF-USR-08`, `RF-USR-09`
- **Descripción:**
  > **Como** miembro activo,  
  > **quiero** configurar mi biografía, avatar, matriz de disponibilidad semanal y modalidad de intercambio (presencial/virtual),  
  > **para** establecer las condiciones en las que puedo realizar intercambios formativos.
- **Vistas Usadas o a Realizar:**
  - **Web Desktop:** `09 - Perfil de Usuario & Matriz de Disponibilidad Semanal` y `21 - Disponibilidad, Agenda y Horarios Semanales`
  - **Mobile Responsive:** `11 - Mobile Perfil de Usuario & Matriz Semanal` y `23 - Mobile Disponibilidad y Agenda`
  - **Alcance Visual:** Vista Completa — En 09/11 edición de biografía, avatar y modalidad; en 21/23 editor completo de franjas de 30 min, toggles por día, sincronización GCal y buffer de descanso
- **Criterios de Aceptación:**
  - **Backend:**
    - [ ] Tablas relacionales `user_profiles` y `user_availabilities` (día de la semana, hora inicio, hora fin).
    - [ ] Endpoints documentados en Swagger UI (`/docs`):
      - `GET /api/users/me/profile`: Perfil personal y preferencias.
      - `PUT /api/users/me/profile`: Actualización total.
      - `PATCH /api/users/me/profile`: Actualización parcial (avatar o biografía).
      - `GET /api/users/me/availability`: Grilla horaria del miembro.
      - `PUT /api/users/me/availability`: Reemplazo de matriz semanal completa.
      - `DELETE /api/users/me/availability/{id}`: Elimina franja horaria específica.
    - [ ] Validación de que el miembro autenticado solo puede modificar sus propios recursos (`/me`).
  - **Frontend:**
    - [ ] Store de perfil y agenda en **Zustand**.
    - [ ] Pantalla de edición de perfil con pestañas (Datos personales, Horarios, Preferencias).
    - [ ] Selector interactivo de bloques horarios semanales (grilla de lunes a domingo).
    - [ ] Selector de modalidad (Virtual, Presencial con radio en kilómetros, o Ambas).
    - [ ] Enlace "Mi Perfil y Horarios" accesible en el Sidebar para miembros y administradores.
    - [ ] Notificaciones toast que muestran el `message` devuelto por el backend.
    - [ ] Diseño 100% responsive en mobile, tablet y desktop.

---

#### HU-14: Registro de habilidades que el miembro enseña (Nivel Declarado y Tarifa en Puntos)
- **Épica:** `EPIC-04: Catálogo y Habilidades`
- **Actor Principal:** Miembro Instructor
- **Roles Permitidos:** `UserRole.MEMBER`, `UserRole.ADMIN`
- **Sprint:** Sprint 1
- **Estado:** Por hacer
- **Puntos de Historia:** 5
- **Prioridad:** Alta
- **Trazabilidad:** `RF-HAB-02`, `RF-HAB-04`, `RF-HAB-05`
- **Descripción:**
  > **Como** miembro instructor,  
  > **quiero** asociar a mi perfil habilidades del catálogo que puedo enseñar indicando nivel declarado, experiencia y tarifa opcional en puntos por hora para clases no recíprocas,  
  > **para** ponerlas a disposición de la comunidad tanto para intercambio como para clases remuneradas en puntos.
- **Vistas Usadas o a Realizar:**
  - **Web Desktop:** `09 - Perfil de Usuario & Matriz de Disponibilidad Semanal`
  - **Mobile Responsive:** `11 - Mobile Perfil de Usuario & Matriz Semanal`
  - **Alcance Visual:** Solo una parte de esa vista — Sección 'Habilidades que enseño' en el perfil, con nivel declarado 1-5, años de experiencia, badge no verificado y tarifa horaria opcional en puntos
- **Criterios de Aceptación:**
  - **Backend:**
    - [ ] Tabla `user_teaching_skills` con restricción de unicidad compuesta `UNIQUE(user_id, skill_id)`.
    - [ ] Campos agregados: `hourly_points_rate` (entero $\ge 0$, tarifa en puntos por hora para clases no recíprocas).
    - [ ] Validación de `years_of_experience`: número entero en rango válido (0 a 60 años).
    - [ ] Validación de `declared_level`: restringido al enum (`BEGINNER`, `INTERMEDIATE`, `ADVANCED`, `EXPERT`).
    - [ ] Estado inicial asignado automáticamente como `DECLARADA`.
    - [ ] Endpoints documentados en Swagger UI (`/docs`):
      - `GET /api/users/me/teaching-skills`: Lista de habilidades con `count`.
      - `POST /api/users/me/teaching-skills`: Registra nueva habilidad ofrecida y su costo opcional en puntos.
      - `PUT /api/users/me/teaching-skills/{id}`: Actualiza descripción, experiencia, nivel y tarifa en puntos.
      - `DELETE /api/users/me/teaching-skills/{id}`: Elimina la habilidad ofrecida.
  - **Frontend:**
    - [ ] Store de habilidades ofrecidas en **Zustand**.
    - [ ] Modal con autocompletado de catálogo, sliders de experiencia y campo para definir costo en puntos por hora para clases pagas.
    - [ ] Lista en el perfil con distintivo visual claro que aclara que el nivel no ha sido verificado por IA.
    - [ ] Enlace "Mis Habilidades a Enseñar" visible en el Sidebar para miembros autenticados.
    - [ ] Avisos de éxito/error renderizando el `message` del backend.
    - [ ] Diseño 100% responsive en mobile, tablet y desktop.

---

#### HU-15: Registro de habilidades que el miembro desea aprender
- **Épica:** `EPIC-04: Catálogo y Habilidades`
- **Actor Principal:** Miembro Aprendiz
- **Roles Permitidos:** `UserRole.MEMBER`, `UserRole.ADMIN`
- **Sprint:** Sprint 1
- **Estado:** Por hacer
- **Puntos de Historia:** 3
- **Prioridad:** Alta
- **Trazabilidad:** `RF-HAB-03`
- **Descripción:**
  > **Como** miembro aprendiz,  
  > **quiero** registrar las habilidades que deseo adquirir indicando mi nivel de partida y nivel meta,  
  > **para** que el motor de emparejamiento me conecte con instructores compatibles para intercambio o pago con puntos.
- **Vistas Usadas o a Realizar:**
  - **Web Desktop:** `09 - Perfil de Usuario & Matriz de Disponibilidad Semanal`
  - **Mobile Responsive:** `11 - Mobile Perfil de Usuario & Matriz Semanal`
  - **Alcance Visual:** Solo una parte de esa vista — Sección 'Habilidades que deseo aprender' en el perfil, con nivel actual vs nivel meta y etiqueta de urgencia
- **Criterios de Aceptación:**
  - **Backend:**
    - [ ] Tabla `user_learning_skills` con restricción de unicidad `UNIQUE(user_id, skill_id)`.
    - [ ] Validación lógica: el `target_level` debe ser estrictamente superior o igual al `current_level`.
    - [ ] Validación de `urgency`: restringido al enum (`LOW`, `MEDIUM`, `HIGH`).
    - [ ] Endpoints documentados en Swagger UI (`/docs`):
      - `GET /api/users/me/learning-skills`: Listado de demandas con `count`.
      - `POST /api/users/me/learning-skills`: Agrega habilidad a aprender.
      - `PUT /api/users/me/learning-skills/{id}`: Actualiza niveles y urgencia.
      - `DELETE /api/users/me/learning-skills/{id}`: Remueve habilidad deseada.
  - **Frontend:**
    - [ ] Store de **Zustand** para demandas de aprendizaje.
    - [ ] Sección interactiva en el perfil con tarjetas y etiquetas de nivel.
    - [ ] Enlace "Quiero Aprender" accesible en el Sidebar para miembros autenticados.
    - [ ] Feedback visual con el `message` emitido por el backend.
    - [ ] Diseño 100% responsive en mobile, tablet y desktop.

---

#### HU-16: Portafolio de evidencias externas para habilidades
- **Épica:** `EPIC-04: Catálogo y Habilidades`
- **Actor Principal:** Miembro Instructor
- **Roles Permitidos:** `UserRole.MEMBER`, `UserRole.ADMIN`
- **Sprint:** Sprint 1
- **Estado:** Por hacer
- **Puntos de Historia:** 3
- **Prioridad:** Media
- **Trazabilidad:** `RF-HAB-08`
- **Descripción:**
  > **Como** miembro con experiencia previa,  
  > **quiero** adjuntar enlaces de respaldo (repositorios, videos, certificados) a mis habilidades ofrecidas,  
  > **para** reforzar la confianza de los interesados antes de la evaluación formal.
- **Vistas Usadas o a Realizar:**
  - **Web Desktop:** `09 - Perfil de Usuario` y `10 - Pasaporte de Habilidades: Reporte de Auditoría Pública`
  - **Mobile Responsive:** `11 - Mobile Perfil de Usuario` y `12 - Mobile Pasaporte de Habilidades Público`
  - **Alcance Visual:** Solo una parte de esa vista — Componente de evidencias externas y enlaces a repositorios/certificados dentro de la tarjeta de habilidad y en el dossier público
- **Criterios de Aceptación:**
  - **Backend:**
    - [ ] Tabla `skill_evidences` con validación de URL y tipología de recurso.
    - [ ] Endpoints documentados en Swagger UI (`/docs`):
      - `GET /api/users/me/teaching-skills/{id}/evidences`: Consulta evidencias asociadas.
      - `POST /api/users/me/teaching-skills/{id}/evidences`: Añade enlace/evidencia.
      - `PUT /api/users/me/teaching-skills/{id}/evidences/{evidence_id}`: Edita recurso.
      - `DELETE /api/users/me/teaching-skills/{id}/evidences/{evidence_id}`: Elimina evidencia.
  - **Frontend:**
    - [ ] Gestión del listado de evidencias en store de **Zustand**.
    - [ ] Modal accesible desde la tarjeta de habilidad en el perfil con vista previa de enlaces y badges.
    - [ ] Toasts con el `message` de respuesta del backend.
    - [ ] Diseño 100% responsive en mobile, tablet y desktop.

---

#### HU-17: Herramienta multiplataforma de captura para datasets de IA (Web y Móvil)
- **Épica:** `EPIC-05: Datasets e Ingesta de Datos para IA`
- **Actor Principal:** Administrador de la Plataforma
- **Roles Permitidos:** `UserRole.ADMIN`
- **Sprint:** Sprint 1
- **Estado:** Por hacer
- **Puntos de Historia:** 8
- **Prioridad:** Alta
- **Trazabilidad:** `RF-IA-18`
- **Descripción:**
  > **Como** administrador del sistema,  
  > **quiero** una interfaz web y móvil para capturar video, audio y código de pruebas piloto con consentimiento explícito,  
  > **para** alimentar los datasets de entrenamiento internos de música y fútbol desde etapas tempranas.
- **Vistas Usadas o a Realizar:**
  - **Web Desktop:** `19 - Administración de Modelos de IA, Datasets & Desafíos`
  - **Mobile Responsive:** `21 - Mobile Administración de IA & Banco de Desafíos`
  - **Alcance Visual:** Solo una parte de esa vista — Panel de 'Ingesta y Captura de Muestras Multimedia' con subida multipart, hash SHA-256 y metadatos de video, audio y código
- **Criterios de Aceptación:**
  - **Backend:**
    - [ ] Almacenamiento seguro del archivo multimedia temporal en almacenamiento estructurado/MinIO con validación de hash SHA-256.
    - [ ] Registro de metadatos de captura (disciplina, reto, hardware utilizado y consentimiento firmado).
    - [ ] Endpoints documentados en Swagger UI (`/docs`) y protegidos estrictamente para administradores:
      - `GET /api/ai/datasets/samples`: Lista muestras recolectadas con `count` (requiere `ADMIN`).
      - `POST /api/ai/datasets/samples/upload`: Subida multipart validando tamaños y formatos (mp4, wav, py) (requiere `ADMIN`).
      - `DELETE /api/ai/datasets/samples/{id}`: Elimina muestras defectuosas (requiere `ADMIN`).
    - [ ] **Política 404:** Retorno de `statuscode: 404` si un miembro común intenta acceder a estos endpoints.
  - **Frontend:**
    - [ ] Ruta `/admin/capture` protegida: si el usuario no tiene rol `UserRole.ADMIN`, la guardia de ruta renderiza directamente la página **404 Not Found**.
    - [ ] **Restricción en Sidebar:** El módulo "Captura de Datasets" es visible exclusivamente para el rol `UserRole.ADMIN`.
    - [ ] Grabador con acceso nativo a cámara y micrófono mediante Capacitor/Web, temporizador y subida de archivos al backend.
    - [ ] Control de captura multimedia mediante store de **Zustand**.
    - [ ] Alertas que despliegan el `message` exacto del backend tras la subida.
    - [ ] Diseño 100% responsive en mobile, tablet y desktop.

---

#### HU-18: Consola de etiquetado y anotación de muestras por Administradores
- **Épica:** `EPIC-05: Datasets e Ingesta de Datos para IA`
- **Actor Principal:** Administrador de la Plataforma
- **Roles Permitidos:** `UserRole.ADMIN`
- **Sprint:** Sprint 1
- **Estado:** Por hacer
- **Puntos de Historia:** 5
- **Prioridad:** Media
- **Trazabilidad:** `RF-IA-02`, `RF-IA-19`
- **Descripción:**
  > **Como** administrador del equipo de IA,  
  > **quiero** una consola para reproducir muestras capturadas y calificarlas pericialmente,  
  > **para** generar el *ground truth* del dataset con métricas técnicas rigurosas.
- **Vistas Usadas o a Realizar:**
  - **Web Desktop:** `19 - Administración de Modelos de IA, Datasets & Desafíos`
  - **Mobile Responsive:** `21 - Mobile Administración de IA & Banco de Desafíos`
  - **Alcance Visual:** Solo una parte de esa vista — Consola central de 'Etiquetado y Anotación Ground Truth' con reproductor frame a frame, registro de toques y desviación acústica
- **Criterios de Aceptación:**
  - **Backend:**
    - [ ] Tabla `dataset_annotations` con métricas por vertical (toques válidos en fútbol, afinación/tiempo en música).
    - [ ] Endpoints documentados en Swagger UI (`/docs`):
      - `GET /api/ai/datasets/samples/pending-annotation`: Entrega muestras pendientes (requiere `ADMIN`).
      - `POST /api/ai/datasets/annotations`: Registra calificación pericial (requiere `ADMIN`).
      - `PUT /api/ai/datasets/annotations/{id}`: Corrige anotación antes del cierre (requiere `ADMIN`).
    - [ ] **Política 404:** Retorno de `statuscode: 404` si un miembro no administrador intenta acceder.
  - **Frontend:**
    - [ ] Ruta `/admin/labeling` restringida: si el usuario tiene rol `MEMBER`, la guardia de ruta renderiza directamente la página **404 Not Found**.
    - [ ] **Restricción en Sidebar:** Apartado "Consola de Etiquetado" visible solo para `UserRole.ADMIN`.
    - [ ] Consola web con reproductor de video/audio frame a frame y controles para asentar métricas.
    - [ ] Estado de la cola de anotación manejado con **Zustand**.
    - [ ] Notificaciones basadas en el `message` recibido de la API.
    - [ ] Diseño 100% responsive en mobile, tablet y desktop.

---

#### HU-19: Versionado y exportación de particiones de datasets (Train/Val/Test)
- **Épica:** `EPIC-05: Datasets e Ingesta de Datos para IA`
- **Actor Principal:** Administrador de la Plataforma
- **Roles Permitidos:** `UserRole.ADMIN`
- **Sprint:** Sprint 1
- **Estado:** Por hacer
- **Puntos de Historia:** 5
- **Prioridad:** Alta
- **Trazabilidad:** `RF-IA-01`, `RF-IA-03`, `RF-IA-21`
- **Descripción:**
  > **Como** administrador de modelos de IA,  
  > **quiero** compilar las muestras etiquetadas en un dataset versionado con división balanceada (Train, Val, Test),  
  > **para** entrenar los clasificadores de PyTorch de manera reproducible y científica.
- **Vistas Usadas o a Realizar:**
  - **Web Desktop:** `19 - Administración de Modelos de IA, Datasets & Desafíos`
  - **Mobile Responsive:** `21 - Mobile Administración de IA & Banco de Desafíos`
  - **Alcance Visual:** Solo una parte de esa vista — Sección de 'Particionamiento Estratificado 70/15/15', control de versiones congeladas y exportación de manifiestos JSON/CSV para PyTorch
- **Criterios de Aceptación:**
  - **Backend:**
    - [ ] Particionamiento automático con ratios estratificados por nivel (ej. 70% Train, 15% Validation, 15% Test).
    - [ ] Validación de balance de clases y eliminación de archivos corruptos o truncados.
    - [ ] Endpoints documentados en Swagger UI (`/docs`) y protegidos estrictamente para administradores:
      - `GET /api/ai/datasets`: Listado de datasets con `count` (requiere `ADMIN`).
      - `POST /api/ai/datasets/versions`: Genera y congela versión (requiere `ADMIN`).
      - `GET /api/ai/datasets/{id}/export`: Descarga paquete o manifiesto JSON/CSV (requiere `ADMIN`).
      - `DELETE /api/ai/datasets/{id}`: Descarta versión obsoleta (requiere `ADMIN`).
    - [ ] **Política 404:** Respuestas `statuscode: 404` ante llamadas no autorizadas.
  - **Frontend:**
    - [ ] Ruta `/admin/datasets` protegida: si el usuario no tiene rol `UserRole.ADMIN`, la guardia de ruta renderiza directamente la página **404 Not Found**.
    - [ ] **Restricción en Sidebar:** Sección "Gestión de Datasets" visible únicamente para administradores.
    - [ ] Panel administrativo con gráficos de distribución de clases y botón de descarga de versión del dataset.
    - [ ] Store de datasets en **Zustand**.
    - [ ] Feedback visual consumiendo el `message` emitido por el backend.
    - [ ] Diseño 100% responsive en mobile, tablet y desktop.

---

### SPRINT 2: Búsqueda Avanzada, Matching Bidireccional y WebSockets

#### HU-20: Búsqueda de usuarios por habilidad y filtros multidimensionales
- **Épica:** `EPIC-06: Búsqueda y Matching`
- **Actor Principal:** Miembro Aprendiz
- **Roles Permitidos:** `UserRole.MEMBER`, `UserRole.ADMIN`
- **Sprint:** Sprint 2
- **Estado:** Por hacer
- **Puntos de Historia:** 5
- **Prioridad:** Alta
- **Trazabilidad:** `RF-MAT-01`, `RF-MAT-02`, `RF-MAT-11`
- **Descripción:**
  > **Como** miembro aprendiz,  
  > **quiero** buscar instructores aplicando filtros de habilidad, nivel, verificación, modalidad y distancia geográfica,  
  > **para** hallar perfiles idóneos para el intercambio.
- **Vistas Usadas o a Realizar:**
  - **Web Desktop:** `02 - Resultados de Búsqueda & Filtros Dinámicos`
  - **Mobile Responsive:** `03 - Mobile Búsqueda y Resultados` y `04 - Mobile Drawer de Filtros Avanzados`
  - **Alcance Visual:** Vista Completa — Buscador facetado, panel lateral / drawer de filtros multidimensionales (categoría, nivel, radio geográfico, modalidad y solo verificados)
- **Criterios de Aceptación:**
  - **Backend:**
    - [ ] Endpoints documentados en Swagger UI (`/docs`):
      - `GET /api/search/tutors`: Búsqueda facetada con parámetros (`skill_id`, `verified_only`, `modality`, `max_distance`, `page`, `page_size`) y campo `count` total optimizado con índices.
    - [ ] Soporte para filtro estricto de instructores con habilidades verificadas por IA (`verified_only=true`).
  - **Frontend:**
    - [ ] Ruta `/search` protegida para usuarios autenticados.
    - [ ] **Restricción en Sidebar:** Enlace "Explorar Instructores" visible en la navegación de miembros.
    - [ ] Panel de filtros laterales con Shadcn Mist y grilla responsiva de tarjetas de instructores con sellos de verificación y tarifa en puntos.
    - [ ] Store de búsqueda y filtros sincronizado con **Zustand**.
    - [ ] Mensajes de retroalimentación consumidos desde el `message` del backend.
    - [ ] Diseño 100% responsive en mobile, tablet y desktop.

---

#### HU-21: Motor de coincidencia bidireccional recíproca ($A \leftrightarrow B$)
- **Épica:** `EPIC-06: Búsqueda y Matching`
- **Actor Principal:** Miembro de la Comunidad
- **Roles Permitidos:** `UserRole.MEMBER`, `UserRole.ADMIN`
- **Sprint:** Sprint 2
- **Estado:** Por hacer
- **Puntos de Historia:** 8
- **Prioridad:** Alta
- **Trazabilidad:** `RF-MAT-03`
- **Descripción:**
  > **Como** miembro de SkillMatch,  
  > **quiero** que la plataforma detecte automáticamente a personas cuyas habilidades enseñadas coinciden con las que busco y viceversa,  
  > **para** recibir sugerencias de intercambio de beneficio mutuo directo.
- **Vistas Usadas o a Realizar:**
  - **Web Desktop:** `01 - Shell Maestro Web`, `02 - Resultados de Búsqueda` y `03 - Modal de Cadenas Triangulares`
  - **Mobile Responsive:** `01 - Mobile Feed`, `03 - Mobile Búsqueda` y `05 - Mobile Modal Cadena Triangular`
  - **Alcance Visual:** Solo una parte de esa vista — Feed de sugerencias automáticas en columna central de 01, algoritmo de compatibilidad en 02 y modal de trueque triangular en 03/05
- **Criterios de Aceptación:**
  - **Backend:**
    - [ ] Consulta relacional optimizada que detecta cruces bidireccionales entre `user_teaching_skills` y `user_learning_skills`.
    - [ ] Generación automática de registros de coincidencia en la tabla `matches` en estado `pending` previniendo duplicados.
    - [ ] Endpoints documentados en Swagger UI (`/docs`):
      - `GET /api/matches/suggestions`: Coincidencias sugeridas para el miembro con `count`.
      - `GET /api/matches/{id}`: Detalle de la coincidencia.
    - [ ] Restricción para que cada miembro solo acceda a sus propias sugerencias de match.
  - **Frontend:**
    - [ ] Ruta `/matches` protegida en React Router.
    - [ ] **Restricción en Sidebar:** Enlace "Mis Coincidencias" en el menú principal de miembro.
    - [ ] Vista dedicada "Tus Coincidencias" mostrando los emparejamientos encontrados con sus respectivas habilidades cruzadas.
    - [ ] Store de coincidencias en **Zustand**.
    - [ ] Renderizado en pantalla del `message` del backend.
    - [ ] Diseño 100% responsive en mobile, tablet y desktop.

---

#### HU-22: Cálculo y explicabilidad del score de compatibilidad (%)
- **Épica:** `EPIC-06: Búsqueda y Matching`
- **Actor Principal:** Miembro de la Comunidad
- **Roles Permitidos:** `UserRole.MEMBER`, `UserRole.ADMIN`
- **Sprint:** Sprint 2
- **Estado:** Por hacer
- **Puntos de Historia:** 5
- **Prioridad:** Alta
- **Trazabilidad:** `RF-MAT-04`, `RF-MAT-06`
- **Descripción:**
  > **Como** miembro evaluando propuestas de match,  
  > **quiero** ver un porcentaje de compatibilidad y los factores que lo justifican,  
  > **para** entender el grado de afinidad antes de aceptar el intercambio.
- **Vistas Usadas o a Realizar:**
  - **Web Desktop:** `02 - Resultados de Búsqueda & Filtros Dinámicos` y `03B - Crear Propuesta de Intercambio & Horario`
  - **Mobile Responsive:** `03 - Mobile Búsqueda y Resultados` y `05B - Mobile Crear Propuesta de Intercambio`
  - **Alcance Visual:** Solo una parte de esa vista — Badge de compatibilidad porcentual (96%) y desglose explicativo de factores (afinidad 40%, horarios 25%, modalidad 20%, reputación 15%)
- **Criterios de Aceptación:**
  - **Backend:**
    - [ ] Función determinística de scoring basada en matriz ponderada:
      - Afinidad de habilidades ofrecidas/buscadas (40%).
      - Coincidencia de disponibilidad horaria (25%).
      - Compatibilidad de modalidad y ubicación (20%).
      - Nivel de verificación y reputación previa (15%).
    - [ ] Endpoint documentado en Swagger UI (`/docs`):
      - `GET /api/matches/{id}/compatibility`: Retorna desglose porcentual y lista explicativa (`match_reasons`: ["Ambos disponibles fines de semana", "Habilidad verificada"]).
    - [ ] Verificación de pertenencia del miembro al match consultado (404 Not Found si es ajeno).
  - **Frontend:**
    - [ ] Gestión visual del score en el store de **Zustand**.
    - [ ] Medidor visual de afinidad (barra circular Shadcn Mist) y tooltip con las razones del match mostrando el `message` y variables del backend.
    - [ ] Diseño 100% responsive en mobile, tablet y desktop.

---

#### HU-23: Tarjeta de coincidencia (*Match Card*) con acciones de aceptar y rechazar
- **Épica:** `EPIC-06: Búsqueda y Matching`
- **Actor Principal:** Miembro de la Comunidad
- **Roles Permitidos:** `UserRole.MEMBER`, `UserRole.ADMIN`
- **Sprint:** Sprint 2
- **Estado:** Por hacer
- **Puntos de Historia:** 5
- **Prioridad:** Alta
- **Trazabilidad:** `RF-MAT-05`, `RF-MAT-07`
- **Descripción:**
  > **Como** miembro con sugerencias de match,  
  > **quiero** ver la tarjeta comparativa de lo que ambos ofrecemos y aprenderemos, y poder aceptar o declinar la propuesta,  
  > **para** formalizar el inicio del intercambio cuando ambos coincidan.
- **Vistas Usadas o a Realizar:**
  - **Web Desktop:** `01 - Shell Maestro Web`, `03B - Crear Propuesta`, `03C - Revisión de Propuesta Recibida` y `03D - Modal Intercambio Aceptado`
  - **Mobile Responsive:** `01 - Mobile Feed`, `05B - Crear Propuesta`, `05C - Revisión de Propuesta` y `05D - Modal Intercambio Aceptado`
  - **Alcance Visual:** Vista Completa en 03B, 03C y 03D / 05B, 05C y 05D — Flujo completo: tarjeta comparativa de trueque, selección de horarios, revisión bilateral con botones de Aceptar/Contraproponer/Rechazar y modal de confirmación
- **Criterios de Aceptación:**
  - **Backend:**
    - [ ] Endpoints documentados en Swagger UI (`/docs`):
      - `POST /api/matches/{id}/accept`: Acepta la propuesta.
      - `POST /api/matches/{id}/decline`: Declina la propuesta.
      - `DELETE /api/matches/{id}`: Descarta la sugerencia.
    - [ ] Lógica de transición de estado: cuando ambos miembros aceptan, el match cambia a `confirmed` y se habilita el canal de contacto.
    - [ ] Verificación estricta de que el miembro autenticado es parte del match.
  - **Frontend:**
    - [ ] Componente visual de Match Card interactivo mostrando foto, nombres, habilidades cruzadas y sellos de verificación.
    - [ ] Estado de tarjetas y animaciones manejado mediante **Zustand**.
    - [ ] Toasts de confirmación renderizando el `message` emitido por el backend.
    - [ ] Diseño 100% responsive en mobile, tablet y desktop.

---

#### HU-24: Conexión WebSocket para notificaciones y eventos en tiempo real
- **Épica:** `EPIC-07: Notificaciones y Tiempo Real`
- **Actor Principal:** Usuario Autenticado
- **Roles Permitidos:** `UserRole.MEMBER`, `UserRole.ADMIN`
- **Sprint:** Sprint 2
- **Estado:** Por hacer
- **Puntos de Historia:** 5
- **Prioridad:** Alta
- **Trazabilidad:** `RF-NOT-01`
- **Descripción:**
  > **Como** miembro o administrador conectado a la plataforma,  
  > **quiero** recibir avisos instantáneos ante nuevos matches, confirmaciones y mensajes,  
  > **para** estar enterado sin tener que recargar la página.
- **Vistas Usadas o a Realizar:**
  - **Web Desktop:** Topbar_Sticky_FacebookStyle en todas las pantallas Web (`01` a `30`)
  - **Mobile Responsive:** Mobile_Header_Top en todas las pantallas Mobile (`01` a `32`)
  - **Alcance Visual:** Solo una parte de esa vista — Icono de campana interactivo con punto indicador en tiempo real y toasts emergentes de eventos WebSocket
- **Criterios de Aceptación:**
  - **Backend:**
    - [ ] Protocolo y endpoints documentados en Swagger UI (`/docs`):
      - `GET /api/notifications/ws-token`: Genera ticket temporal para handshake autenticado.
      - `WebSocket /ws/notifications`: Canal dúplex con canalización dirigida por usuario autenticado.
    - [ ] Emisión de eventos: `MATCH_RECEIVED`, `MATCH_CONFIRMED`, `SESSION_PROPOSED`, `POINTS_RECEIVED`.
    - [ ] Rechazo inmediato del handshake si el ticket no contiene un rol válido.
  - **Frontend:**
    - [ ] Hook de cliente WebSocket con soporte para reconexión automática ante microcortes.
    - [ ] Store de WebSockets y eventos en vivo en **Zustand**.
    - [ ] Notificaciones toast emergentes reflejando el `message` del evento entrante.
    - [ ] Diseño 100% responsive en mobile, tablet y desktop.

---

#### HU-25: Bandeja de notificaciones y configuración de preferencias
- **Épica:** `EPIC-07: Notificaciones y Tiempo Real`
- **Actor Principal:** Usuario Autenticado
- **Roles Permitidos:** `UserRole.MEMBER`, `UserRole.ADMIN`
- **Sprint:** Sprint 2
- **Estado:** Por hacer
- **Puntos de Historia:** 3
- **Prioridad:** Media
- **Trazabilidad:** `RF-NOT-03`
- **Descripción:**
  > **Como** miembro habitual,  
  > **quiero** ver el histórico de mis notificaciones no leídas y configurar qué tipos de alertas recibir,  
  > **para** gestionar mi bandeja de entrada de forma personalizada.
- **Vistas Usadas o a Realizar:**
  - **Web Desktop:** `25 - Bandeja de Notificaciones & Eventos`
  - **Mobile Responsive:** `27 - Mobile Bandeja de Notificaciones`
  - **Alcance Visual:** Vista Completa — Panel desplegable con histórico de alertas filtrable por no leídas, intercambios y puntos, con opción de marcar todas como leídas
- **Criterios de Aceptación:**
  - **Backend:**
    - [ ] Endpoints documentados en Swagger UI (`/docs`):
      - `GET /api/notifications`: Avisos del miembro con paginación y `count`.
      - `PATCH /api/notifications/{id}/read`: Marca una como leída.
      - `PATCH /api/notifications/read-all`: Marca todas como leídas.
      - `DELETE /api/notifications/{id}`: Elimina notificación.
      - `PUT /api/users/me/notification-preferences`: Actualiza canales permitidos (push, in-app).
  - **Frontend:**
    - [ ] Popover en el navbar superior con campana de avisos, contador dinámico de no leídas y vista `/notifications/settings`.
    - [ ] Bandeja y preferencias sincronizadas en store de **Zustand**.
    - [ ] Alertas renderizando el `message` del backend.
    - [ ] Diseño 100% responsive en mobile, tablet y desktop.

---

#### HU-26: Bloqueo preventivo y reporte de usuarios
- **Épica:** `EPIC-06: Búsqueda y Matching`
- **Actor Principal:** Miembro de la Comunidad
- **Roles Permitidos:** `UserRole.MEMBER`, `UserRole.ADMIN`
- **Sprint:** Sprint 2
- **Estado:** Por hacer
- **Puntos de Historia:** 3
- **Prioridad:** Alta
- **Trazabilidad:** `RF-MAT-14`, `RF-NOT-06`
- **Descripción:**
  > **Como** miembro que detecta una interacción indebida,  
  > **quiero** bloquear y reportar a ese usuario,  
  > **para** cesar todo contacto y enviar la incidencia a moderación.
- **Vistas Usadas o a Realizar:**
  - **Web Desktop:** `26 - Modal Reporte y Bloqueo de Usuario` y `27 - Perfil Bloqueado (Acciones Restringidas)`
  - **Mobile Responsive:** `28 - Mobile Modal Reporte y Bloqueo` y `29 - Mobile Perfil Bloqueado`
  - **Alcance Visual:** Vista Completa — En 26/28 modal de reporte con selección de infracción; en 27/29 interfaz del perfil bloqueado con banner de sanción y todos los botones de acción desactivados con candado
- **Criterios de Aceptación:**
  - **Backend:**
    - [ ] Endpoints documentados en Swagger UI (`/docs`):
      - `GET /api/users/blocked`: Usuarios bloqueados con `count`.
      - `POST /api/users/{id}/block`: Bloquea usuario y anula matches previos.
      - `DELETE /api/users/{id}/unblock`: Desbloquea usuario.
      - `POST /api/users/{id}/report`: Envía reporte formal con tipología y evidencia a la cola de moderación.
    - [ ] Exclusión automática de usuarios bloqueados en consultas de búsqueda y matching.
  - **Frontend:**
    - [ ] Vista `/settings/privacy` con listado de bloqueos administrada en **Zustand**.
    - [ ] Botón de bloqueo/reporte en tarjetas y perfiles con formulario modal de motivos.
    - [ ] Notificación toast mostrando el `message` del backend.
    - [ ] Diseño 100% responsive en mobile, tablet y desktop.

---

### SPRINT 3: Evaluación de Programación, Sandbox y Anti-Fraude

#### HU-27: Banco de reactivos teóricos y examen aleatorio
- **Épica:** `EPIC-08: Evaluación de Código y Sandbox`
- **Actor Principal:** Miembro Aspirante a Certificación
- **Roles Permitidos:** `UserRole.MEMBER`
- **Sprint:** Sprint 3
- **Estado:** Por hacer
- **Puntos de Historia:** 5
- **Prioridad:** Alta
- **Trazabilidad:** `RF-EVA-02`, `RF-EVA-03`, `RF-FRA-01`, `RF-FRA-02`
- **Descripción:**
  > **Como** postulante a validar programación,  
  > **quiero** rendir un examen teórico con preguntas aleatorias y límite de tiempo estricto,  
  > **para** acreditar mis fundamentos conceptuales antes del reto práctico.
- **Vistas Usadas o a Realizar:**
  - **Web Desktop:** `06 - Preguntas Orales Técnicas con Cámara`
  - **Mobile Responsive:** `08 - Mobile Preguntas con Cámara`
  - **Alcance Visual:** Solo una parte de esa vista — Panel de preguntas teóricas aleatorias con cronómetro regresivo y evaluación conceptual previa al sandbox
- **Criterios de Aceptación:**
  - **Backend:**
    - [ ] Banco de ítems categorizado por nivel y habilidad (opción múltiple y verdadero/falso).
    - [ ] Selección pseudo-aleatoria de preguntas garantizando no repetición entre intentos.
    - [ ] Endpoints documentados en Swagger UI (`/docs`):
      - `POST /api/evaluations/start`: Inicializa sesión de examen con temporizador global y por ítem.
      - `GET /api/evaluations/{id}/questions`: Reactivos aleatorios con `count`.
      - `POST /api/evaluations/{id}/answers`: Registra respuesta del aspirante bajo tiempo límite.
      - `GET /api/evaluations/{id}/status`: Consulta progreso y tiempo restante.
    - [ ] Validación de que la evaluación pertenece exclusivamente al miembro autenticado.
  - **Frontend:**
    - [ ] Ruta `/evaluation/:id/theory` protegida por `UserRole.MEMBER` bajo Layout de examen en pantalla completa (ocultando Sidebar y barras distractoras).
    - [ ] Interfaz con barra de progreso, cuenta regresiva visual y bloqueo de navegación accidental.
    - [ ] Store de la evaluación teórica en **Zustand** (cronómetro, pregunta activa, respuestas).
    - [ ] Notificaciones con el `message` del backend si se agota el tiempo o se procesa la respuesta.
    - [ ] Diseño 100% responsive en mobile, tablet y desktop.

---

#### HU-28: Editor web de código y ejecutor en Sandbox Docker aislado
- **Épica:** `EPIC-08: Evaluación de Código y Sandbox`
- **Actor Principal:** Miembro Aspirante a Certificación
- **Roles Permitidos:** `UserRole.MEMBER`
- **Sprint:** Sprint 3
- **Estado:** Por hacer
- **Puntos de Historia:** 8
- **Prioridad:** Alta
- **Trazabilidad:** `RF-EVA-05`
- **Descripción:**
  > **Como** miembro rindiendo el reto de programación,  
  > **quiero** escribir mi solución en un editor integrado y ejecutar casos de prueba en un contenedor aislado con validaciones de seguridad y rendimiento,  
  > **para** validar que mi algoritmo resuelve correctamente el problema sin vulnerar el sistema.
- **Vistas Usadas o a Realizar:**
  - **Web Desktop:** `05 - Sandbox de Evaluación de Código (Paso 1: Resolución)`
  - **Mobile Responsive:** `07 - Mobile Sandbox de Código (Paso 1: Resolución)`
  - **Alcance Visual:** Vista Completa — Layout de examen en pantalla completa: Monaco Editor, panel de consigna, consola de ejecución Pytest 4/4 passed y contenedor Docker aislado
- **Criterios de Aceptación:**
  - **Backend (Sandbox Worker & Validaciones):**
    - [ ] Endpoints documentados en Swagger UI (`/docs`):
      - `POST /api/evaluations/{id}/code/run`: Ejecuta pruebas públicas preliminares en sandbox.
      - `POST /api/evaluations/{id}/code/submit`: Entrega final del código contra la suite completa.
      - `GET /api/evaluations/{id}/code/test-results`: Consulta resultados detallados.
    - [ ] Validación de payload de código: tamaño máximo permitido de 64 KB y encoding UTF-8 válido.
    - [ ] Validación de sintaxis previa con AST: si el código contiene errores de sintaxis (`SyntaxError`), se rechaza de inmediato con el error de línea sin consumir tiempo de CPU del sandbox.
    - [ ] Análisis estático previo de seguridad: detección y bloqueo de llamadas a módulos prohibidos (`os.system`, `subprocess`, `socket`, `eval`, `exec`, manipulación directa del filesystem o red).
    - [ ] Contenedor Docker efímero con ejecución no privilegiada (*rootless*), sin acceso a red externa, límites de CPU (1 core), memoria máxima (128 MB) y timeout de 3 segundos contra bucles infinitos o *fork bombs*.
    - [ ] Ejecución de casos de prueba automáticos devolviendo resultados estructurados (pass, fail, salida, tiempos de runtime).
  - **Frontend:**
    - [ ] Ruta `/evaluation/:id/code` protegida por rol en Layout de examen sin navegación externa.
    - [ ] Editor integrado (Monaco Editor / CodeMirror) con resaltado sintáctico, consola de salida y botón de ejecución de tests.
    - [ ] Store de código y estado de ejecución en **Zustand**.
    - [ ] Feedback en consola que refleja el `message` del backend.
    - [ ] Diseño 100% responsive en mobile, tablet y desktop.

---

#### HU-29: Análisis estático de código por AST y métricas de complejidad
- **Épica:** `EPIC-08: Evaluación de Código y Sandbox`
- **Actor Principal:** Miembro Aspirante a Certificación
- **Roles Permitidos:** `UserRole.MEMBER`
- **Sprint:** Sprint 3
- **Estado:** Por hacer
- **Puntos de Historia:** 5
- **Prioridad:** Alta
- **Trazabilidad:** `RF-EVA-06`, `RF-IA-06`
- **Descripción:**
  > **Como** motor de evaluación de IA propia para código,  
  > **quiero** procesar la solución entregada mediante el AST de Python y métricas estáticas,  
  > **para** medir complejidad ciclomática, legibilidad y buenas prácticas sin recurrir a LLMs externos.
- **Vistas Usadas o a Realizar:**
  - **Web Desktop:** `05 - Sandbox de Evaluación de Código` y `07 - Dictamen y Emisión del Sello Verificado`
  - **Mobile Responsive:** `07 - Mobile Sandbox de Código` y `09 - Mobile Dictamen y Sello Verificado`
  - **Alcance Visual:** Solo una parte de esa vista — Widget de métricas estáticas en la consola de 05/07 (complejidad ciclomática de McCabe, profundidad de anidamiento) y reporte consolidado en 07/09
- **Criterios de Aceptación:**
  - **Backend:**
    - [ ] Parser a AST con el módulo nativo `ast` de Python con validación de árbol sintáctico balanceado.
    - [ ] Cálculo de métricas: complejidad ciclomática de McCabe, profundidad máxima de anidamiento (máximo 4 niveles recomendado), cantidad de ramas y reuso de variables.
    - [ ] Detección de antipatrones (variables no utilizadas, código inalcanzable, funciones excesivamente largas).
    - [ ] Puntuación normalizada de calidad técnica de la solución (0 a 100).
    - [ ] Endpoints documentados en Swagger UI (`/docs`):
      - `POST /api/evaluations/{id}/code/ast-analysis`: Ejecuta el análisis sintáctico por AST.
      - `GET /api/evaluations/{id}/code/metrics`: Retorna métricas cuantitativas calculadas.
  - **Frontend:**
    - [ ] Métricas técnicas almacenadas y consumidas desde el store de **Zustand**.
    - [ ] Reporte visual de métricas estáticas en la pantalla de revisión de la prueba con indicadores semafóricos y el `message` explicativo del backend.
    - [ ] Diseño 100% responsive en mobile, tablet y desktop.

---

#### HU-30: Defensa de la solución mediante plantillas parametrizadas por AST
- **Épica:** `EPIC-08: Evaluación de Código y Sandbox`
- **Actor Principal:** Miembro Aspirante a Certificación
- **Roles Permitidos:** `UserRole.MEMBER`
- **Sprint:** Sprint 3
- **Estado:** Por hacer
- **Puntos de Historia:** 5
- **Prioridad:** Media
- **Trazabilidad:** `RF-EVA-07 ★`, `RF-IA-23`
- **Descripción:**
  > **Como** sistema evaluador,  
  > **quiero** plantear preguntas específicas basadas en las variables y estructuras del AST del miembro para que responda por texto,  
  > **para** comprobar que entiende su código y descartar soluciones copiadas.
- **Vistas Usadas o a Realizar:**
  - **Web Desktop:** `06 - Preguntas Orales Técnicas con Cámara`
  - **Mobile Responsive:** `08 - Mobile Preguntas con Cámara`
  - **Alcance Visual:** Vista Completa — Pantalla de defensa oral/escrita con preguntas ancladas a las líneas de código del aspirante, cámara web, medidor VU de audio y transcripción Whisper
- **Criterios de Aceptación:**
  - **Backend:**
    - [ ] Generador determinístico de preguntas parametrizadas según nodos del AST (ej. "¿Por qué utilizaste un bucle en la línea X en lugar de Y?").
    - [ ] Clasificador con heurísticas de procesamiento de lenguaje natural clásico (coincidencia de términos clave técnicos) para validar la respuesta textual del aspirante.
    - [ ] Endpoints documentados en Swagger UI (`/docs`):
      - `GET /api/evaluations/{id}/defense/questions`: Retorna preguntas por AST con `count`.
      - `POST /api/evaluations/{id}/defense/submit`: Recibe y valida explicaciones bajo cronómetro estricto.
  - **Frontend:**
    - [ ] Vista `/evaluation/:id/defense` bajo Layout de examen.
    - [ ] Sección de "Defensa del Código" con visualización del fragmento referenciado y campo de respuesta con tiempo límite.
    - [ ] Flujo de defensa y temporizador en store de **Zustand**.
    - [ ] Alertas que despliegan el `message` del backend.
    - [ ] Diseño 100% responsive en mobile, tablet y desktop.

---

#### HU-31: Detección de pérdida de foco, cambio de pestaña y bloqueo de portapapeles
- **Épica:** `EPIC-09: Supervisión y Prevención de Fraude`
- **Actor Principal:** Sistema Supervisor / Auditoría
- **Roles Permitidos:** `UserRole.MEMBER`
- **Sprint:** Sprint 3
- **Estado:** Por hacer
- **Puntos de Historia:** 3
- **Prioridad:** Alta
- **Trazabilidad:** `RF-FRA-03`, `RF-FRA-09`
- **Descripción:**
  > **Como** sistema de integridad,  
  > **quiero** bloquear el portapapeles y registrar cualquier cambio de pestaña o ventana minimizada,  
  > **para** impedir que el aspirante busque respuestas externas durante la prueba.
- **Vistas Usadas o a Realizar:**
  - **Web Desktop:** `08B - Advertencia Preventiva Anti-Fraude (Aviso 1 de 2)` y `08 - Detección de Trampa e Infracción Anti-Fraude`
  - **Mobile Responsive:** `10B - Mobile Advertencia Preventiva Anti-Fraude` y `10 - Mobile Alerta Detección de Trampa`
  - **Alcance Visual:** Vista Completa — Modal de advertencia preventiva ámbar tras primer blur/paste en 08B/10B, y modal terminal rojo de expulsión con bloqueo de 7 días en 08/10
- **Criterios de Aceptación:**
  - **Backend:**
    - [ ] Endpoints documentados en Swagger UI (`/docs`):
      - `POST /api/evaluations/{id}/incidents`: Registra incidencia con tipo y timestamp en la tabla `evaluation_incidents`.
      - `GET /api/evaluations/{id}/incidents`: Consulta histórico con `count`.
  - **Frontend:**
    - [ ] Desactivación de eventos del portapapeles (`copy`, `paste`, `cut`) y menú contextual (`contextmenu`) dentro del Layout de examen.
    - [ ] Listener de eventos `visibilitychange` y `window.onblur`.
    - [ ] Envío inmediato de incidencia vía API ante pérdida de foco con alerta visual de advertencia.
    - [ ] Store de **Zustand** que registra incidentes y despliega advertencias con el `message` del backend.
    - [ ] Diseño 100% responsive en mobile, tablet y desktop.

---

#### HU-32: Verificación de entorno y prueba de vida (*Liveness*) con cámara
- **Épica:** `EPIC-09: Supervisión y Prevención de Fraude`
- **Actor Principal:** Miembro Aspirante a Certificación
- **Roles Permitidos:** `UserRole.MEMBER`
- **Sprint:** Sprint 3
- **Estado:** Por hacer
- **Puntos de Historia:** 5
- **Prioridad:** Alta
- **Trazabilidad:** `RF-FRA-07`, `RF-FRA-08`
- **Descripción:**
  > **Como** plataforma que certifica habilidades auténticas,  
  > **quiero** verificar periféricos y solicitar un gesto motor aleatorio antes de iniciar la evaluación,  
  > **para** confirmar que la prueba la rinde una persona viva en tiempo real y no una fotografía estática.
- **Vistas Usadas o a Realizar:**
  - **Web Desktop:** `04C - Pre-embarque: Paso 3 (Calibración y Validación)`
  - **Mobile Responsive:** `06C - Mobile Pre-embarque: Paso 3 (Calibración)`
  - **Alcance Visual:** Vista Completa — Paso 3 del stepper: comprobación de webcam, micrófono, iluminación y reto motor aleatorio de prueba de vida con OpenCV
- **Criterios de Aceptación:**
  - **Backend (OpenCV Service):**
    - [ ] Verificación de flujo óptico y coherencia de movimiento en video corto antes de autorizar el examen.
    - [ ] Endpoints documentados en Swagger UI (`/docs`):
      - `POST /api/evaluations/{id}/liveness/check`: Valida ráfaga de frames de movimiento gestual.
      - `GET /api/evaluations/{id}/environment/verify`: Confirma condiciones mínimas de cámara y luz.
  - **Frontend:**
    - [ ] Asistente interactivo guiado por store de **Zustand** en ruta `/evaluation/:id/setup`.
    - [ ] Verificación de periféricos: cámara web, micrófono, iluminación y encuadre del rostro.
    - [ ] Reto interactivo guiado solicitando un movimiento aleatorio (ej. parpadear dos veces, girar levemente el rostro a la derecha).
    - [ ] Indicaciones y mensajes en pantalla utilizando el `message` del backend.
    - [ ] Diseño 100% responsive en mobile, tablet y desktop.

---

#### HU-33: Consolidación de evaluación y otorgamiento del Sello Verificado
- **Épica:** `EPIC-08: Evaluación de Código y Sandbox`
- **Actor Principal:** Miembro Evaluado
- **Roles Permitidos:** `UserRole.MEMBER`
- **Sprint:** Sprint 3
- **Estado:** Por hacer
- **Puntos de Historia:** 5
- **Prioridad:** Alta
- **Trazabilidad:** `RF-EVA-17`, `RF-EVA-18`, `RF-EVA-19 ★`
- **Descripción:**
  > **Como** miembro evaluado,  
  > **quiero** recibir mi calificación ponderada, el reporte del Entrenador de IA con sugerencias y mi sello de certificación,  
  > **para** exhibir mi nivel verificado en mi perfil.
- **Vistas Usadas o a Realizar:**
  - **Web Desktop:** `07 - Dictamen y Emisión del Sello Verificado` y `22 - Mis Certificados de IA & Sellos Verificados`
  - **Mobile Responsive:** `09 - Mobile Dictamen y Sello Verificado` y `24 - Mobile Mis Certificados de IA`
  - **Alcance Visual:** Vista Completa — En 07/09 pantalla de dictamen con desglose ponderado, feedback del Entrenador de IA y sello verificado; en 22/24 galería de certificados y hashes SHA-256
- **Criterios de Aceptación:**
  - **Backend:**
    - [ ] Consolidación de notas: parte teórica (30%), solución funcional de código (50%), métricas estáticas/defensa (20%) y penalización por incidencias de fraude.
    - [ ] Asignación de nivel (Principiante / Intermedio / Avanzado) y cambio de estado a `VERIFICADA`.
    - [ ] Generación de reporte de feedback del Entrenador de IA (`RF-EVA-19 ★`) con reglas/plantillas.
    - [ ] Endpoints documentados en Swagger UI (`/docs`):
      - `POST /api/evaluations/{id}/finalize`: Procesa el cálculo y nota final.
      - `GET /api/evaluations/{id}/result`: Retorna reporte formativo y desglose.
      - `GET /api/users/me/certificates`: Lista sellos y certificados obtenidos con `count`.
  - **Frontend:**
    - [ ] Vista `/evaluation/:id/result` accesible tras finalizar la prueba.
    - [ ] Pantalla de resultados con gráficos de desempeño y visualización del nuevo sello verificado otorgado.
    - [ ] **Sidebar:** Notificación o badge dinámico en "Mis Habilidades" indicando la nueva certificación obtenida.
    - [ ] Vista de resultados administrada con store de **Zustand**.
    - [ ] Despliegue del `message` del backend y de los sellos obtenidos.
    - [ ] Diseño 100% responsive en mobile, tablet y desktop.

---

#### HU-34: Consola administrativa para auditoría de fraudes y apelaciones
- **Épica:** `EPIC-09: Supervisión y Prevención de Fraude`
- **Actor Principal:** Administrador de la Plataforma
- **Roles Permitidos:** `UserRole.ADMIN`
- **Sprint:** Sprint 3
- **Estado:** Por hacer
- **Puntos de Historia:** 3
- **Prioridad:** Alta
- **Trazabilidad:** `RF-FRA-16`, `RF-FRA-17`, `RF-FRA-18`
- **Descripción:**
  > **Como** administrador del sistema,  
  > **quiero** revisar la bitácora de incidencias de evaluaciones dudosas y resolver apelaciones de miembros,  
  > **para** velar por la rigurosidad y transparencia de las certificaciones.
- **Vistas Usadas o a Realizar:**
  - **Web Desktop:** `17 - Consola Forense de Auditoría Anti-Fraude & Apelaciones`
  - **Mobile Responsive:** `19 - Mobile Auditoría Forense de Fraude`
  - **Alcance Visual:** Vista Completa — Consola administrativa SaaS con listado de exámenes sospechosos, bitácora segundo a segundo de telemetría, lectura de apelaciones del alumno y botones de dictamen
- **Criterios de Aceptación:**
  - **Backend:**
    - [ ] Endpoints documentados en Swagger UI (`/docs`) y protegidos estrictamente para administradores:
      - `GET /api/admin/evaluations/suspicious`: Lista pruebas sospechosas con `count` (requiere `ADMIN`).
      - `PATCH /api/admin/evaluations/{id}/verdict`: Ratifica o anula sanción (`CONFIRM_FRAUD`, `DISMISS_FRAUD`) (requiere `ADMIN`).
      - `POST /api/evaluations/{id}/appeal`: Envía solicitud formal de apelación con justificación (requiere `MEMBER`).
      - `PATCH /api/admin/evaluations/{id}/appeal`: Dictamina la apelación presentada (requiere `ADMIN`).
    - [ ] **Política 404:** Retorno de `statuscode: 404` si un miembro común intenta acceder a endpoints `/api/admin/evaluations/...`.
  - **Frontend:**
    - [ ] Ruta `/admin/audit` protegida: si el usuario no tiene rol `UserRole.ADMIN`, la guardia de ruta renderiza directamente la página **404 Not Found**.
    - [ ] **Restricción en Sidebar:** Apartado "Auditoría de Evaluaciones" visible únicamente para administradores.
    - [ ] Vista administrativa con timeline cronológico de eventos (focos perdidos, advertencias) y botones de resolución.
    - [ ] Panel de auditoría administrado con store de **Zustand**.
    - [ ] Notificaciones toast reflejando el `message` del backend.
    - [ ] Diseño 100% responsive en mobile, tablet y desktop.

---

### SPRINT 4: IA de Música y Fútbol, Sesiones, Billetera y Centro de Quejas

#### HU-35: Inferencia y evaluación acústica para instrumentos (librosa/PyTorch)
- **Épica:** `EPIC-10: Modelos de IA para Música y Deportes`
- **Actor Principal:** Miembro Aspirante a Certificación Musical
- **Roles Permitidos:** `UserRole.MEMBER`
- **Sprint:** Sprint 4
- **Estado:** Por hacer
- **Puntos de Historia:** 8
- **Prioridad:** Alta
- **Trazabilidad:** `RF-EVA-09`, `RF-EVA-10`, `RF-IA-05`
- **Descripción:**
  > **Como** evaluador musical,  
  > **quiero** procesar la pista de audio grabada durante la ejecución del instrumento,  
  > **para** medir afinación (pitch), ritmo/tempo y limpieza acústica frente al patrón esperado.
- **Vistas Usadas o a Realizar:**
  - **Web Desktop:** `16B - Modal Crear Nueva Habilidad`, `19 - Datasets` y `22 - Certificados IA`
  - **Mobile Responsive:** `18B - Mobile Modal Nueva Habilidad`, `21 - Datasets` y `24 - Certificados IA`
  - **Alcance Visual:** Solo una parte de esa vista — Parametrización de la rúbrica acústica en 16B/18B, ingesta y etiquetado espectral en 19/21 y credencial de audio en 22/24
- **Criterios de Aceptación:**
  - **Backend (Audio Worker):**
    - [ ] Extracción de espectrogramas Mel y cromas usando `librosa`.
    - [ ] Inferencia de modelo convolucional propio entrenado sobre el dataset interno.
    - [ ] Cuantificación de métricas: desviación de afinación en centésimas de semitono y estabilidad de tempo en BPM.
    - [ ] Endpoints documentados en Swagger UI (`/docs`):
      - `POST /api/evaluations/{id}/audio/upload`: Carga de pista WAV.
      - `POST /api/evaluations/{id}/audio/analyze`: Dispara inferencia acústica.
      - `GET /api/evaluations/{id}/audio/metrics`: Retorna métricas cuantitativas.
  - **Frontend:**
    - [ ] Ruta `/evaluation/:id/music` protegida bajo Layout de examen.
    - [ ] Grabador con metrónomo visual previo y subida de la pista para su análisis.
    - [ ] Grabador gestionado mediante store de **Zustand**.
    - [ ] Visualización del resultado con el `message` devuelto por el backend.
    - [ ] Diseño 100% responsive en mobile, tablet y desktop.

---

#### HU-36: Inferencia y evaluación deportiva para retos de fútbol (OpenCV/PyTorch)
- **Épica:** `EPIC-10: Modelos de IA para Música y Deportes`
- **Actor Principal:** Miembro Aspirante a Certificación Deportiva
- **Roles Permitidos:** `UserRole.MEMBER`
- **Sprint:** Sprint 4
- **Estado:** Por hacer
- **Puntos de Historia:** 8
- **Prioridad:** Alta
- **Trazabilidad:** `RF-EVA-12`, `RF-EVA-13`, `RF-IA-04`
- **Descripción:**
  > **Como** evaluador deportivo,  
  > **quiero** analizar el video grabado de un reto de toques y dominio de balón,  
  > **para** contabilizar repeticiones válidas, control motriz y estabilidad técnica mediante visión artificial.
- **Vistas Usadas o a Realizar:**
  - **Web Desktop:** `16B - Modal Crear Nueva Habilidad`, `19 - Datasets` y `22 - Certificados IA`
  - **Mobile Responsive:** `18B - Mobile Modal Nueva Habilidad`, `21 - Datasets` y `24 - Certificados IA`
  - **Alcance Visual:** Solo una parte de esa vista — Parametrización del reto deportivo en 16B/18B, etiquetado de toques en 19/21 y certificación de habilidades motrices en 22/24
- **Criterios de Aceptación:**
  - **Backend (Vision Worker):**
    - [ ] Inferencia de modelo propio/extractor declarado para keypoints corporales y detección esférica de balón.
    - [ ] Algoritmo de máquina de estados para contar repeticiones basadas en trayectorias e impactos físicos.
    - [ ] Generación de score de desempeño con índice de confianza estadística (`RF-EVA-24`).
    - [ ] Endpoints documentados en Swagger UI (`/docs`):
      - `POST /api/evaluations/{id}/video/upload`: Carga de video MP4.
      - `POST /api/evaluations/{id}/video/analyze`: Inferencia de tracking de balón y pose.
      - `GET /api/evaluations/{id}/video/metrics`: Entrega conteo y métricas motrices.
  - **Frontend:**
    - [ ] Ruta `/evaluation/:id/sports` protegida bajo Layout de examen.
    - [ ] Grabador con silueta guía de encuadre en pantalla y resumen visual de repeticiones contabilizadas.
    - [ ] Asistente de encuadre y subida coordinado mediante store de **Zustand**.
    - [ ] Despliegue de métricas con el `message` oficial del backend.
    - [ ] Diseño 100% responsive en mobile, tablet y desktop.

---

#### HU-37: Detección de múltiples rostros y voces accesorias durante evaluaciones
- **Épica:** `EPIC-09: Supervisión y Prevención de Fraude`
- **Actor Principal:** Sistema Supervisor / Anti-Fraude
- **Roles Permitidos:** `UserRole.MEMBER`
- **Sprint:** Sprint 4
- **Estado:** Por hacer
- **Puntos de Historia:** 5
- **Prioridad:** Alta
- **Trazabilidad:** `RF-FRA-05`, `RF-FRA-06`
- **Descripción:**
  > **Como** sistema supervisor durante pruebas con cámara y micrófono,  
  > **quiero** alertar si aparece más de una persona en pantalla o se escuchan voces accesorias,  
  > **para** evitar asistencia externa ilícita.
- **Vistas Usadas o a Realizar:**
  - **Web Desktop:** `06 - Preguntas Orales Técnicas con Cámara` y `08 - Detección de Trampa e Infracción Anti-Fraude`
  - **Mobile Responsive:** `08 - Mobile Preguntas con Cámara` y `10 - Mobile Alerta Detección de Trampa`
  - **Alcance Visual:** Solo una parte de esa vista — Caja de video con algoritmo de detección facial múltiple y medidor VU de actividad vocal en 06/08, y modal de sanción si se confirma intrusión en 08/10
- **Criterios de Aceptación:**
  - **Backend:**
    - [ ] Detección facial continua en frames seleccionados con alerta ante `count(faces) > 1` o `count(faces) == 0`.
    - [ ] Detección de actividad vocal (VAD) en segundo plano para identificar susurros o voces extrañas durante la ejecución.
    - [ ] Endpoints documentados en Swagger UI (`/docs`):
      - `POST /api/evaluations/{id}/stream/detect-anomalies`: Analiza frames y fragmentos de audio en busca de anomalías.
  - **Frontend:**
    - [ ] Monitoreo en vivo conectado a store de **Zustand**.
    - [ ] Notificaciones de advertencia en vivo en la pantalla si se pierde el rostro o se detecta intrusión.
    - [ ] Alertas dinámicas reflejando el `message` del backend.
    - [ ] Diseño 100% responsive en mobile, tablet y desktop.

---

#### HU-38: Agendamiento, control de cupos gratuitos de 1 hora y cancelaciones auditadas
- **Épica:** `EPIC-11: Sesiones de Intercambio, Reputación y Pasaporte`
- **Actor Principal:** Miembros con Match Confirmado
- **Roles Permitidos:** `UserRole.MEMBER`
- **Sprint:** Sprint 4
- **Estado:** Por hacer
- **Puntos de Historia:** 5
- **Prioridad:** Alta
- **Trazabilidad:** `RF-SES-02`, `RF-SES-03`, `RF-SES-06`
- **Descripción:**
  > **Como** miembro con match confirmado,  
  > **quiero** agendar sesiones de hasta 1 hora consumiendo mi cupo gratuito semanal (o pagando con puntos si excedo el cupo), y cancelar con motivo justificado restaurando mi cupo,  
  > **para** coordinar mis clases con equidad y protección contra cancelaciones abusivas.
- **Vistas Usadas o a Realizar:**
  - **Web Desktop:** `03B`, `03C`, `03D`, `20 - Mis Intercambios` y `21 - Disponibilidad y Horarios`
  - **Mobile Responsive:** `05B`, `05C`, `05D`, `22 - Mis Intercambios` y `23 - Disponibilidad y Agenda`
  - **Alcance Visual:** Vista Completa — Selección de franjas de 1h, control del cupo gratuito de 2 sesiones/semana, cancelación justificada y agenda sincronizada con Google Calendar
- **Criterios de Aceptación:**
  - **Backend:**
    - [ ] Regla de sesión gratuita: duración máxima de 60 minutos y tope de **2 sesiones gratuitas por persona por semana**.
    - [ ] Descuento automático del cupo semanal al momento exacto de crear la agenda (`POST /api/sessions`). Si el usuario no tiene cupo disponible, exige pago en puntos.
    - [ ] Cancelación obligatoria con motivo (`cancellation_reason`):
      - Si la cancelación es válida y oportuna, se **restaura automáticamente la sesión gratuita** de la semana.
      - Registro de cancelaciones mensuales: si el miembro acumula cancelaciones reiteradas (más de 3 al mes o sobre la hora), se activa un bloqueo temporal de 7 días para agendar.
    - [ ] Endpoints documentados en Swagger UI (`/docs`):
      - `GET /api/sessions`: Listado con `count` y detalle de cupos semanales restantes (`free_sessions_left`).
      - `POST /api/sessions`: Agendar sesión (valida cupo o puntos).
      - `POST /api/sessions/{id}/cancel`: Cancelación con `cancellation_reason` obligatorio.
      - `PUT /api/sessions/{id}/reschedule`: Reprogramación de fecha/hora.
      - `PATCH /api/sessions/{id}/status`: Aceptación o rechazo.
  - **Frontend:**
    - [ ] Widget en Sidebar/Navbar: *"Sesiones gratuitas restantes esta semana: X/2 (máx. 1h c/u)"*.
    - [ ] Calendario interactivo de agendamiento y modal estricto de cancelación con campo de motivo obligatorio.
    - [ ] Store de citas en **Zustand**.
    - [ ] Toasts con el `message` del backend y diseño 100% responsive.

---

#### HU-39: Confirmación recíproca post-sesión y registro de horas
- **Épica:** `EPIC-11: Sesiones de Intercambio, Reputación y Pasaporte`
- **Actor Principal:** Participantes de la Sesión
- **Roles Permitidos:** `UserRole.MEMBER`
- **Sprint:** Sprint 4
- **Estado:** Por hacer
- **Puntos de Historia:** 3
- **Prioridad:** Alta
- **Trazabilidad:** `RF-SES-07`, `RF-SES-12`
- **Descripción:**
  > **Como** participante de una sesión de intercambio concluida,  
  > **quiero** confirmar que el encuentro se realizó e indicar las horas efectivas,  
  > **para** que el intercambio impacte formalmente en mi historial y se liberen los puntos si fue una clase paga.
- **Vistas Usadas o a Realizar:**
  - **Web Desktop:** `11A - Sesión Virtual`, `11B - Sesión Presencial` y `12 - Modal Reseña Pedagógica`
  - **Mobile Responsive:** `13A - Sesión Virtual`, `13B - Sesión Presencial` y `14 - Modal Reseña`
  - **Alcance Visual:** Vista Completa — En 11A/13A fin de llamada y confirmación dual; en 11B/13B verificación mutua con PIN de 4 dígitos (7 4 9 2) y liberación automática de Escrow
- **Criterios de Aceptación:**
  - **Backend:**
    - [ ] Endpoint `POST /api/sessions/{id}/confirm` que transiciona a `COMPLETED` únicamente con la confirmación de ambas partes.
    - [ ] Liberación automática de los puntos en custodia (*escrow*) a la billetera del tutor al completarse la confirmación dual.
    - [ ] Registro de inasistencias (*no-shows*) con penalización automática de reputación.
    - [ ] Endpoints documentados en Swagger UI (`/docs`):
      - `POST /api/sessions/{id}/confirm`: Confirmación de realización y horas.
      - `POST /api/sessions/{id}/report-noshow`: Reporte de inasistencia injustificada.
  - **Frontend:**
    - [ ] Modal de confirmación post-sesión con checklist de temas abordados y duración cumplida.
    - [ ] Modal coordinado con store de **Zustand**.
    - [ ] Alertas mostrando el `message` del backend.
    - [ ] Diseño 100% responsive en mobile, tablet y desktop.

---

#### HU-40: Calificaciones mutuas, propinas voluntarias en puntos y Puntaje de Confianza (★)
- **Épica:** `EPIC-11: Sesiones de Intercambio, Reputación y Pasaporte`
- **Actor Principal:** Participantes de la Sesión / Comunidad
- **Roles Permitidos:** 
  - Calificar y dar propina: `UserRole.MEMBER`
  - Consultar reputación: Público / `UserRole.MEMBER`, `UserRole.ADMIN`
- **Sprint:** Sprint 4
- **Estado:** Por hacer
- **Puntos de Historia:** 5
- **Prioridad:** Alta
- **Trazabilidad:** `RF-REP-01`, `RF-REP-02 ★`
- **Descripción:**
  > **Como** miembro que terminó una clase,  
  > **quiero** calificar a mi compañero y tener la opción de regalarle puntos como propina,  
  > **para** premiar a los tutores excepcionales y construir un ecosistema de alta confianza.
- **Vistas Usadas o a Realizar:**
  - **Web Desktop:** `12 - Modal Reseña Pedagógica & Propinas SkillPoints` y `23 - Reputación, Reseñas y Propinas`
  - **Mobile Responsive:** `14 - Mobile Modal Reseña Pedagógica` y `25 - Mobile Reputación y Reseñas`
  - **Alcance Visual:** Vista Completa — En 12/14 formulario modal con 3 criterios de 5 estrellas y pills de propina (0, +5, +10, +25 SP); en 23/25 muro público con score 4.9★ y testimonios
- **Criterios de Aceptación:**
  - **Backend:**
    - [ ] Tabla `session_reviews` con puntuaciones por criterios (puntualidad, pedagogía, dominio) y comentarios con filtro anti-lenguaje ofensivo.
    - [ ] Endpoint para envío de propina voluntaria: `POST /api/sessions/{id}/tip`: debita puntos de la billetera del alumno y los transfiere a la billetera del tutor con transacción tipo `TIP`.
    - [ ] Algoritmo de Puntaje de Confianza consolidando: verificaciones superadas por IA (40%), feedback de pares (30%), asistencia (20%) y antigüedad (10%).
    - [ ] Endpoints documentados en Swagger UI (`/docs`):
      - `GET /api/sessions/{id}/review`: Consulta estado de reseña.
      - `POST /api/sessions/{id}/review`: Emite calificación bilateral.
      - `POST /api/sessions/{id}/tip`: Transfiere propina en puntos.
      - `GET /api/users/{id}/reputation`: Retorna Puntaje de Confianza e insignias.
  - **Frontend:**
    - [ ] Formulario de calificación obligatoria (estrellas) con componente opcional: *"¿Deseas dejarle una propina a tu tutor?"* con selectores rápidos de puntos (10, 25, 50 puntos o monto personalizado).
    - [ ] Indicador de confianza e insignias visibles en perfiles de miembro y tarjetas de búsqueda.
    - [ ] Store de **Zustand** que actualiza el saldo de puntos tras dar la propina.
    - [ ] Diseño 100% responsive en mobile, tablet y desktop.

---

#### HU-41: Emisión y consulta pública del Pasaporte de Habilidades con Código QR (★)
- **Épica:** `EPIC-11: Sesiones de Intercambio, Reputación y Pasaporte`
- **Actor Principal:** Miembro Certificado (Titular) / Terceros y Empleadores (Consultores)
- **Roles Permitidos:** 
  - Consulta pública: Público (Sin autenticación)
  - Gestión/Generación QR y PDF: `UserRole.MEMBER`
- **Sprint:** Sprint 4
- **Estado:** Por hacer
- **Puntos de Historia:** 5
- **Prioridad:** Media
- **Trazabilidad:** `RF-HAB-11 ★`, `RF-HAB-12 ★`
- **Descripción:**
  > **Como** miembro con habilidades certificadas por SkillMatch,  
  > **quiero** disponer de mi Pasaporte de Habilidades accesible por enlace público y código QR verificable,  
  > **para** compartir mis competencias certificadas con terceros o en mi currículum profesional.
- **Vistas Usadas o a Realizar:**
  - **Web Desktop:** `10 - Pasaporte de Habilidades: Reporte de Auditoría Pública` y `09 - Perfil de Usuario`
  - **Mobile Responsive:** `12 - Mobile Pasaporte de Habilidades Público` y `11 - Mobile Perfil`
  - **Alcance Visual:** Vista Completa — En 10/12 dossier técnico 'Recruiter-Grade' público con código, Pytest, transcripción oral y hash; en 09/11 generador de QR específico por habilidad
- **Criterios de Aceptación:**
  - **Backend:**
    - [ ] Endpoints documentados en Swagger UI (`/docs`):
      - `GET /api/passports/{public_uuid}`: Consulta pública de competencias verificadas (pública, sin token).
      - `GET /api/passports/{public_uuid}/qr`: Genera el código QR dinámico apuntando a la URL firmada.
      - `GET /api/passports/{public_uuid}/pdf`: Genera y descarga el pasaporte firmado institucionalmente en PDF.
  - **Frontend:**
    - [ ] Ruta `/passport/:uuid` pública sin requerir login con diseño credencial de alta gama (estilo Shadcn Mist).
    - [ ] **Restricción en Sidebar:** Enlace "Mi Pasaporte de Habilidades" visible para el miembro autenticado en su menú de perfil.
    - [ ] Vista de pasaporte administrada en store de **Zustand** con código QR interactivo y botón de descarga en PDF.
    - [ ] Feedback visual consumiendo el `message` del backend.
    - [ ] Diseño 100% responsive en mobile, tablet y desktop.

---

#### HU-42: Billetera de Puntos: Recarga, pago de clases y retiro de dinero (Cashout)
- **Épica:** `EPIC-12: Economía de Puntos, Billetera y Resolución de Quejas`
- **Actor Principal:** Miembro de la Comunidad
- **Roles Permitidos:** `UserRole.MEMBER`
- **Sprint:** Sprint 4
- **Estado:** Por hacer
- **Puntos de Historia:** 8
- **Prioridad:** Alta
- **Trazabilidad:** Modelo de Monetización, RF-SES-09
- **Descripción:**
  > **Como** miembro de SkillMatch,  
  > **quiero** comprar paquetes de puntos con dinero real para pagar clases no recíprocas, y poder retirar en dinero real a mi cuenta bancaria las ganancias obtenidas por enseñar y recibir propinas,  
  > **para** aprender sin depender de tener una habilidad recíproca y monetizar mis conocimientos de forma transparente.
- **Vistas Usadas o a Realizar:**
  - **Web Desktop:** `13A - Billetera de Tokens & Balance Escrow`, `13B - Modal Adquisición` y `13C - Modal Canje y Retiro`
  - **Mobile Responsive:** `15A - Mobile Billetera`, `15B - Modal Adquisición` y `15C - Modal Canje y Retiro`
  - **Alcance Visual:** Vista Completa — En 13A/15A dashboard de saldo y Escrow; en 13B/15B compra de paquetes con pasarela; en 13C/15C retiro de propinas a cuenta bancaria
- **Criterios de Aceptación:**
  - **Backend:**
    - [ ] Modelos `Wallet`, `PointTransaction` (tipos: `TOPUP`, `CLASS_PAYMENT`, `TIP`, `CASHOUT`, `ADMIN_REWARD`) y `CashoutRequest` (estados: `PENDING`, `APPROVED`, `REJECTED`).
    - [ ] Integración con pasarela de pago para compra de paquetes de puntos (ej. 100 puntos = $10 USD).
    - [ ] Bloqueo de puntos en custodia (*escrow*) al agendar clase no recíproca y liberación automática al tutor al completarse la sesión (`POST /api/sessions/{id}/pay`).
    - [ ] Solicitud de retiro de dinero (`POST /api/wallet/cashout`): valida saldo mínimo para retiro, calcula la comisión por servicio de la plataforma (ej. 15%) y genera la solicitud de transferencia con datos bancarios.
    - [ ] Endpoints documentados en Swagger UI (`/docs`):
      - `GET /api/wallet/balance`: Consulta saldo en puntos y equivalente monetario.
      - `POST /api/wallet/topup`: Recarga de puntos con pasarela de pago.
      - `POST /api/wallet/cashout`: Envía solicitud de retiro a cuenta bancaria.
      - `GET /api/wallet/transactions`: Historial paginado de movimientos con `count`.
  - **Frontend:**
    - [ ] Vista `/wallet` protegida en React Router para miembros.
    - [ ] **Restricción en Sidebar:** Enlace "Mi Billetera" con badge visible del saldo actual en puntos.
    - [ ] Modal de recarga de puntos con selección de paquetes y pasarela de pago integrada.
    - [ ] Formulario de retiro de fondos (Cashout) con cálculo visual en tiempo real de la comisión y monto neto a recibir.
    - [ ] Tabla de historial de transacciones filtrable por tipo gestionada en store de **Zustand**.
    - [ ] Toasts con el `message` del backend y diseño 100% responsive.

---

#### HU-43: Centro de Quejas, Resolución de Disputas y Compensación en Puntos por el Administrador
- **Épica:** `EPIC-12: Economía de Puntos, Billetera y Resolución de Quejas`
- **Actor Principal:** Miembro (Emisión de Queja) / Administrador (Resolución y Compensación)
- **Roles Permitidos:** 
  - Enviar queja: `UserRole.MEMBER`
  - Resolver y compensar: `UserRole.ADMIN`
- **Sprint:** Sprint 4
- **Estado:** Por hacer
- **Puntos de Historia:** 5
- **Prioridad:** Alta
- **Trazabilidad:** Calidad del Servicio y Gobernanza
- **Descripción:**
  > **Como** miembro que experimentó un inconveniente en una sesión o en la plataforma, y como administrador del sistema,  
  > **queremos** un canal formal donde el miembro reporte su queja y el administrador pueda responderle, resolverla y compensarlo con puntos si lo considera oportuno,  
  > **para** brindar una atención justa, resolver disputas y fidelizar a la comunidad.
- **Vistas Usadas o a Realizar:**
  - **Web Desktop:** `24A - Centro de Quejas Usuario`, `24B - Formulario de Apertura de Queja & Pruebas`, `12 - Modal Reseña` y `18 - Centro de Quejas Admin`
  - **Mobile Responsive:** `26A - Mobile Quejas Usuario`, `26B - Mobile Formulario Queja`, `14 - Modal Reseña` y `20 - Mobile Centro Quejas Admin`
  - **Alcance Visual:** Vista Completa — Formulario de denuncia del alumno con pruebas/telemetría en 24B/26B y consola arbitral Master-Detail en 18/20 con botones para Reembolso y Compensación
- **Criterios de Aceptación:**
  - **Backend:**
    - [ ] Modelo `Complaint` vinculado al miembro y opcionalmente a `session_id`, con estados (`OPEN`, `RESOLVED`, `DISMISSED`), `reason`, `description`, `admin_response` y `points_compensated`.
    - [ ] Endpoints documentados en Swagger UI (`/docs`):
      - `POST /api/complaints`: El miembro envía una queja formal vinculando la sesión afectada.
      - `GET /api/complaints/my`: Historial de quejas y respuestas del miembro con `count`.
      - `GET /api/admin/complaints`: Listado administrativo de quejas con filtros por estado y `count` (requiere `ADMIN`).
      - `PATCH /api/admin/complaints/{id}/resolve`: El administrador responde, cierra la queja y opcionalmente asigna puntos de compensación que se acreditan de inmediato en la billetera del miembro con transacción tipo `ADMIN_REWARD` (requiere `ADMIN`).
    - [ ] **Política 404:** Retorno de `statuscode: 404` si un miembro común intenta acceder a endpoints administrativos de quejas.
  - **Frontend:**
    - [ ] Formulario de queja accesible desde el detalle de una sesión o centro de ayuda para el miembro.
    - [ ] Vista `/admin/complaints` protegida: si el usuario no tiene rol `UserRole.ADMIN`, la guardia de ruta renderiza directamente la página **404 Not Found**.
    - [ ] **Restricción en Sidebar:** Apartado "Centro de Quejas" visible únicamente para administradores.
    - [ ] Panel administrativo con detalle del reclamo, editor de respuesta oficial y switch opcional: *"Compensar con Puntos"* con selector de cantidad.
    - [ ] Gestión de estado en store de **Zustand**.
    - [ ] Alertas renderizando el `message` del backend y diseño 100% responsive en mobile, tablet y desktop.
