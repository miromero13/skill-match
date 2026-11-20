# Guía Maestra de Pruebas: Historias de Usuario Finalizadas en Jira (Done)

Este documento detalla **paso a paso cómo probar cada una de las Historias de Usuario en estado "Listo" (Done)** en el Jira de **SkillMatch** (Proyecto `SM`).

---

## 1. Tabla de Credenciales y Roles de Acceso

La plataforma cuenta con un modelo estricto de dos roles (**RBAC**):

| Rol | Método de Acceso | Credenciales / Datos | URLs de Entrada |
| :--- | :--- | :--- | :--- |
| **`ADMIN`** (Administrador) | Correo y Contraseña | **Correo:** `admin@skillmatch.com`<br>**Contraseña:** `Test@123` | [`/admin/login`](http://localhost:5173/admin/login)<br>Dashboard: [`/admin/dashboard`](http://localhost:5173/admin/dashboard) |
| **`MEMBER`** (Miembro / Usuario Final) | Google One-Tap / OAuth | Cuenta de Google del usuario | [`/login`](http://localhost:5173/login)<br>Plataforma: [`/app`](http://localhost:5173/app) |
| **`PÚBLICO`** (Visitante Anónimo) | Libre navegación | Sin autenticación | [`/`](http://localhost:5173/) |

> [!IMPORTANT]
> **Política de Ofuscación 404 (Security by Obfuscation):** Si intentas ingresar a cualquier ruta administrativa (`/admin/...`) estando logueado como `MEMBER` o como visitante anónimo, el sistema retornará **`404 Not Found`** ("Página no encontrada"), jamás un `403 Forbidden`. La existencia de la consola de administración está totalmente oculta para los usuarios comunes.

---

## 2. Requisitos Previos para Probar

1. **Backend en ejecución:**
   ```bash
   cd backend
   source .venv/bin/activate
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
   * Swagger interactivo: [http://localhost:8000/docs](http://localhost:8000/docs)
2. **Frontend en ejecución:**
   ```bash
   cd frontend
   npm run dev
   ```
   * Aplicación Web: [http://localhost:5173](http://localhost:5173)

---

## 3. Matriz de Pruebas por Historia de Usuario en Jira

---

### SM-14 — HU-02: Historias de Usuario y Planificación en Jira
* **Tipo:** Gobernanza Ágil y Gestión.
* **Rol para probar:** N/A (Administrativo en Jira).
* **Cómo probarlo:**
  1. Ingresar a tu espacio de Jira Software: [https://sauterdevs.atlassian.net/jira/software/projects/SM/boards](https://sauterdevs.atlassian.net/jira/software/projects/SM/boards).
  2. Verificar que el backlog cuente con las 12 Épicas parametrizadas, estimaciones Fibonacci y la distribución de los Sprints 0 al 4.

---

### SM-15 — HU-03: Inicialización y Arquitectura Base del Backend
* **Tipo:** Arquitectura y API Backend.
* **Rol para probar:** Libre / Swagger API.
* **URL:** [http://localhost:8000/docs](http://localhost:8000/docs)
* **Cómo probarlo:**
  1. Abrir Swagger UI en `http://localhost:8000/docs`.
  2. Ejecutar el endpoint `GET /api/health`.
  3. Comprobar que responde con HTTP 200 y el sobre unificado `APIResponse`:
     ```json
     {
       "statuscode": 200,
       "message": "Sistema operativo y base de datos conectada exitosamente.",
       "data": { "status": "healthy", "database": "connected" }
     }
     ```
  4. Comprobar que todas las excepciones devuelven `{ "statuscode": 4xx/500, "message": "...", "data": null }`.

---

### SM-16 — HU-04: Inicialización del Frontend y Configuración Móvil con Capacitor
* **Tipo:** Frontend Shell y Multiplataforma.
* **Rol para probar:** Libre / Visitante.
* **URL:** [http://localhost:5173](http://localhost:5173)
* **Cómo probarlo:**
  1. Abrir la consola de desarrollo del navegador (`F12`) y activar la vista adaptable móvil (ej. iPhone 14 o Pixel 7).
  2. Comprobar la identidad visual Shadcn preset **Mist** (paleta fría esmeralda, bordes suaves, fuente Inter).
  3. Probar la navegación a una ruta inexistente como `http://localhost:5173/ruta-aleatoria` y verificar la pantalla dedicada **404 Not Found**.

---

### SM-17 — HU-05: Prototipo Completo del Sistema en Alta Fidelidad
* **Tipo:** Diseño UI/UX.
* **Rol para probar:** N/A (Archivos locales de diseño).
* **Ubicación:** Carpeta [`docs/prototipo/`](file:///Users/ilseromero/Documents/projects/sw1/docs/prototipo/)
* **Cómo probarlo:**
  1. Inspeccionar los mockups exportados en PNG en `docs/prototipo/` o abrir `skillmatch-prototype.op`.
  2. Verificar la cobertura de las 30 pantallas web de escritorio y las 32 pantallas móviles.

---

### SM-18 — HU-06: Landing Page Pública y Presentación de la Plataforma
* **Tipo:** Vista Pública Institucional.
* **Rol para probar:** **PÚBLICO** (sin iniciar sesión).
* **URL:** [http://localhost:5173/](http://localhost:5173/)
* **Qué puedes hacer y cómo probarlo:**
  1. Acceder a `http://localhost:5173/`.
  2. Explorar la sección **Hero** con la propuesta de valor de Skill Swapping validado por IA.
  3. Revisar el flujo explicativo en 3 pasos ("Cómo Funciona").
  4. Observar las demostraciones de las 3 áreas de IA (Programación, Música, Fútbol).
  5. Verificar que el bloque de métricas consume dinámicamente `GET /api/platform/stats` con contadores en vivo.
  6. Probar los botones de acción para ir al Login de miembros o al acceso de administradores en el pie de página.

---

### SM-19 — HU-07: Registro Rápido y Autenticación de Miembros con Google
* **Tipo:** Autenticación de Usuarios.
* **Rol para probar:** **MEMBER** (Usuario final).
* **URL:** [http://localhost:5173/login](http://localhost:5173/login)
* **Qué puedes hacer y cómo probarlo:**
  1. Dirigirse a `http://localhost:5173/login`.
  2. Pulsar sobre el botón **"Continuar con Google"**.
  3. El sistema verificará la identidad y emitirá un token JWT con `role: "MEMBER"`.
  4. Redirección automática a la plataforma de miembros: `http://localhost:5173/app`.
  5. Se crea automáticamente en segundo plano la billetera personal del usuario con saldo inicial de 0 puntos.

---

### SM-20 — HU-08: Autenticación Exclusiva para Administradores
* **Tipo:** Seguridad y Acceso Administrativo.
* **Rol para probar:** **ADMIN**
* **URL:** [http://localhost:5173/admin/login](http://localhost:5173/admin/login)
* **Credenciales:**
  * **Correo:** `admin@skillmatch.com`
  * **Contraseña:** `Test@123`
* **Qué puedes hacer y cómo probarlo:**
  1. Entrar en `http://localhost:5173/admin/login`.
  2. Probar ingresar una contraseña errónea: se alertará el error y el backend incrementará el contador de fallos (bloqueo preventivo tras 5 intentos).
  3. Ingresar las credenciales válidas indicadas.
  4. Al autenticar, el sistema redirige al **Admin Dashboard** (`http://localhost:5173/admin/dashboard`).
  5. Abrir una pestaña en modo incógnito e intentar acceder directamente a `http://localhost:5173/admin/dashboard`: el sistema muestra `404 Not Found`.

---

### SM-21 — HU-09: Gestión de Sesión JWT Unificada y Persistencia
* **Tipo:** Manejo de Sesión y Seguridad.
* **Rol para probar:** **MEMBER** o **ADMIN**.
* **Cómo probarlo:**
  1. Iniciar sesión como miembro o administrador.
  2. Recargar la página (`F5`) o cerrar y reabrir la pestaña del navegador: la sesión permanece activa sin desloguearte (persistencia mediante Storage Adapter).
  3. Pulsar en el botón o menú **"Cerrar Sesión"**.
  4. El sistema revoca el token en el backend (registrado en la tabla `revoked_tokens`) y redirige inmediatamente al login. Intentar volver atrás con las flechas del navegador no permitirá interactuar sin autenticarte.

---

### SM-22 — HU-10: Creación y Gestión de Administradores
* **Tipo:** Administración de Cuentas.
* **Rol para probar:** **ADMIN** (`admin@skillmatch.com` / `Test@123`).
* **URL:** [http://localhost:5173/admin/administrators](http://localhost:5173/admin/administrators)
* **Qué puedes hacer y cómo probarlo:**
  1. Como admin, ingresar a `http://localhost:5173/admin/administrators`.
  2. Observar la tabla con los administradores existentes y sus estados (`Activo`, `Bloqueado`).
  3. Hacer clic en **"Nuevo Administrador"**.
  4. Rellenar el formulario con nombre, correo institucional y contraseña segura (mínimo 8 caracteres, mayúscula, minúscula, número y símbolo).
  5. Crear el administrador y verificar que aparece en el listado.
  6. Probar los botones de acción para bloquear o desbloquear un administrador existente.

---

### SM-24 — HU-12: Catálogo Maestro de Habilidades y Taxonomía
* **Tipo:** Gestión de Contenidos y Taxonomía.
* **Rol para probar:** **ADMIN** (`admin@skillmatch.com` / `Test@123`).
* **URL:** [http://localhost:5173/admin/catalog](http://localhost:5173/admin/catalog)
* **Qué puedes hacer y cómo probarlo:**
  1. Acceder al panel de catálogo en `http://localhost:5173/admin/catalog`.
  2. Observar el árbol jerárquico de categorías (categorías principales y subcategorías anidadas).
  3. Crear una nueva categoría con su descripción y slug.
  4. Crear una nueva habilidad asociada a una categoría (ej. "TypeScript Avanzado", min approval 75%).
  5. Probar registrar una categoría o habilidad con un nombre idéntico pero en mayúsculas/minúsculas o con tildes: el sistema rechazará la duplicación gracias a la normalización de nombres.
  6. Activar o desactivar habilidades y verificar que el estado se actualiza en vivo.

---

### SM-25 — HU-13: Edición de Perfil, Disponibilidad y Enrolamiento Biométrico Facial
* **Tipo:** Perfil de Miembro y Biometría con IA Local.
* **Rol para probar:** **MEMBER** (Inicio de sesión con Google).
* **URLs:**
  * Perfil: [http://localhost:5173/app/profile](http://localhost:5173/app/profile)
  * Disponibilidad: [http://localhost:5173/app/availability](http://localhost:5173/app/availability)
* **Qué puedes hacer y cómo probarlo:**
  1. En `/app/profile`:
     * Modificar nombre completo, biografía, enlaces sociales e idiomas.
     * Seleccionar modalidad de intercambio preferida (**Virtual**, **Presencial** o **Híbrida**).
  2. **Enrolamiento Biométrico Facial Real (OpenCV YuNet + SFace en Python):**
     * En la tarjeta de biometría, pulsar **"Activar Cámara Web"** y conceder permisos.
     * Colocarse frente a la cámara: el sistema calcula en tiempo real (60 fps) la iluminación ambiente y la posición del rostro.
     * Presionar **"Capturar y Vincular Rostro Testigo"**.
     * El backend procesa el frame con YuNet, detecta puntos faciales, extrae el embedding normalizado de 128 dimensiones con SFace y genera un hash SHA-256 persistido en PostgreSQL.
     * Aparecerá el badge verde **"Rostro Testigo Vinculado"**.
  3. En `/app/availability`:
     * Configurar tus bloques horarios semanales disponibles para intercambios de Lunes a Domingo.

---

### SM-26 — HU-14: Registro de Habilidades que el Miembro Enseña
* **Tipo:** Oferta de Habilidades.
* **Rol para probar:** **MEMBER** (Google).
* **URL:** [http://localhost:5173/app/teaching-skills](http://localhost:5173/app/teaching-skills)
* **Qué puedes hacer y cómo probarlo:**
  1. Acceder a `http://localhost:5173/app/teaching-skills`.
  2. Hacer clic en **"Ofrecer Habilidad"**.
  3. Seleccionar una habilidad del catálogo (ej. "Python y FastAPI").
  4. Indicar tu nivel declarado (Principiante, Intermedio, Avanzado, Experto) y tus años de experiencia (0 a 60).
  5. Activar la opción **"Acepto intercambio por puntos"** y definir una tarifa horaria (ej. `25` puntos/hora).
  6. Guardar: la habilidad se registra en estado `DECLARADA`.
  7. *(Validación de integridad):* Si intentas ingresar una tarifa negativa o cero con puntos activados, el sistema la rechazará tanto a nivel frontend como mediante la restricción de base de datos `ck_teaching_rate`.

---

### SM-27 — HU-15: Registro de Habilidades que el Miembro Desea Aprender
* **Tipo:** Demanda de Aprendizaje.
* **Rol para probar:** **MEMBER** (Google).
* **URL:** [http://localhost:5173/app/learning-skills](http://localhost:5173/app/learning-skills)
* **Qué puedes hacer y cómo probarlo:**
  1. Acceder a `http://localhost:5173/app/learning-skills`.
  2. Pulsar **"Agregar Habilidad por Aprender"**.
  3. Seleccionar la habilidad, nivel de partida (1-5), nivel objetivo deseado (debe ser $\ge$ partida) y nivel de urgencia (Baja, Media, Alta).
  4. Agregar una nota u objetivo personal (ej. *"Prepararme para examen final"*).
  5. Guardar y verificar que aparece en tu lista.
  6. **Probar edición y borrado de notas:** Editar la demanda y borrar el contenido de la nota para dejarla vacía; al guardar, la nota se limpia (`null`). Si editas únicamente el nivel o urgencia sin tocar la nota, esta se conservará intacta.

---

### SM-28 — HU-16: Portafolio de Evidencias Externas para Habilidades
* **Tipo:** Evidencias y Acreditación.
* **Rol para probar:** **MEMBER** (Google).
* **URL:** [http://localhost:5173/app/teaching-skills](http://localhost:5173/app/teaching-skills)
* **Qué puedes hacer y cómo probarlo:**
  1. En una tarjeta de habilidad que enseñas, hacer clic en el botón de **"Evidencias" / "Portafolio"**.
  2. Pulsar **"Añadir Evidencia"**.
  3. Seleccionar el tipo de evidencia:
     * **Repositorio** (ej. GitHub / GitLab)
     * **Video** (ej. YouTube demostrativo)
     * **Certificado** (ej. enlace a PDF en Drive o plataforma de cursos)
     * **Otro**
  4. Ingresar un título y la URL (el sistema valida que inicie con `https://` o `http://`).
  5. Verificar que la evidencia se vincula a tu oferta y que no permite registrar la misma URL dos veces para la misma habilidad.

---

### SM-32 — HU-20: Búsqueda de Usuarios por Habilidad y Filtros Multidimensionales
* **Tipo:** Motor de Búsqueda y Filtros.
* **Rol para probar:** **MEMBER** (Google).
* **URL:** [http://localhost:5173/app/search](http://localhost:5173/app/search)
* **Qué puedes hacer y cómo probarlo:**
  1. Ir a `http://localhost:5173/app/search`.
  2. Escribir un término en la barra de búsqueda (ej. *"Python"* o *"Guitarra"*).
  3. Aplicar filtros en el panel lateral o superior:
     * **Modalidad:** Virtual, Presencial o Ambas.
     * **Tarifa máxima en puntos**.
     * **Nivel mínimo del instructor**.
  4. Comprobar que los resultados se actualizan dinámicamente mostrando tarjetas de instructores disponibles.

---

### SM-33 — HU-21: Motor de Coincidencia Bidireccional Recíproca ($A \leftrightarrow B$)
* **Tipo:** Matching de Habilidades.
* **Rol para probar:** **MEMBER** (Google).
* **URL:** [http://localhost:5173/matches](http://localhost:5173/matches)
* **Qué puedes hacer y cómo probarlo:**
  1. Entrar en `http://localhost:5173/matches`.
  2. El sistema analiza automáticamente lo que tú enseñas vs lo que otros buscan y lo que tú buscas vs lo que otros enseñan.
  3. Se despliegan únicamente candidatos que cumplen coincidencia recíproca o con alto grado de afinidad.

---

### SM-34 — HU-22: Cálculo y Explicabilidad del Score de Compatibilidad (%)
* **Tipo:** Algoritmo de Compatibilidad.
* **Rol para probar:** **MEMBER** (Google).
* **URL:** [http://localhost:5173/matches](http://localhost:5173/matches)
* **Qué puedes hacer y cómo probarlo:**
  1. En las sugerencias de `/matches`, observar el badge con porcentaje numérico (ej. `88%`, `94%`).
  2. Hacer clic en **"Ver desglose de compatibilidad"** o sobre la barra de afinidad.
  3. Se desplegará la explicación objetiva y determinística:
     * Puntos por cruce de habilidades (enseño/aprendo).
     * Solapamiento de horarios en la matriz de disponibilidad.
     * Coincidencia de modalidad y proximidad geográfica.

---

### SM-35 — HU-23: Tarjeta de Coincidencia (*Match Card*) con Acciones de Aceptar y Rechazar
* **Tipo:** Interacción de Match.
* **Rol para probar:** **MEMBER** (Google).
* **URL:** [http://localhost:5173/matches](http://localhost:5173/matches)
* **Qué puedes hacer y cómo probarlo:**
  1. En la lista de candidatos de `/matches`, cada tarjeta presenta los datos del perfil, habilidades cruzadas y botones de acción rápida.
  2. **Aceptar / Proponer Intercambio:** Al presionar "Proponer Intercambio", se crea una propuesta formal y se notifica al usuario receptor.
  3. **Descartar / Rechazar:** Al pulsar en la "X" o "Descartar", la tarjeta desaparece de tu bandeja de sugerencias activas.

---

### SM-36 — HU-24: Conexión WebSocket para Notificaciones y Eventos en Tiempo Real
* **Tipo:** Comunicación en Tiempo Real.
* **Rol para probar:** **MEMBER** (Google).
* **URL:** Cualquier vista autenticada (ej. `http://localhost:5173/app`).
* **Qué puedes hacer y cómo probarlo:**
  1. Iniciar sesión con Google.
  2. Abrir las herramientas de desarrollador (`F12`) -> Pestaña **Network** -> Filtro **WS**.
  3. Verificar la conexión WebSocket abierta contra `ws://localhost:8000/ws/notifications`.
  4. Cuando ocurre un evento (nuevo match, solicitud o mensaje), el WebSocket emite el mensaje sin recargar la página:
     * Aparece inmediatamente una alerta tipo Toast en la esquina de la pantalla.
     * Se actualiza en vivo el badge numérico de la campana en la barra superior.

---

### SM-37 — HU-25: Bandeja de Notificaciones y Configuración de Preferencias
* **Tipo:** Centro de Notificaciones.
* **Rol para probar:** **MEMBER** (Google).
* **URLs:**
  * Bandeja: [http://localhost:5173/notifications](http://localhost:5173/notifications)
  * Ajustes: [http://localhost:5173/notifications/settings](http://localhost:5173/notifications/settings)
* **Qué puedes hacer y cómo probarlo:**
  1. En `/notifications`:
     * Consultar el listado cronológico de avisos clasificados por tipo (Intercambios, Seguridad, Mensajes).
     * Probar hacer clic en una notificación para marcarla como leída.
     * Probar el botón **"Marcar todas como leídas"**.
  2. En `/notifications/settings`:
     * Activar o desactivar interruptores (Switches) para silenciar o permitir notificaciones específicas (nuevas propuestas, recordatorios de sesión o mensajes).

---

### SM-38 — HU-26: Bloqueo Preventivo y Reporte de Usuarios
* **Tipo:** Moderación y Seguridad de la Comunidad.
* **Rol para probar:** **MEMBER** (Google).
* **URL:** [http://localhost:5173/app/search](http://localhost:5173/app/search) o menú de usuario en Match Cards.
* **Qué puedes hacer y cómo probarlo:**
  1. En la tarjeta de perfil de cualquier usuario en búsqueda o matching, abrir el menú de tres puntos (`...`).
  2. Seleccionar **"Bloquear usuario"** o **"Reportar usuario"**:
     * Al reportar, seleccionar la categoría (Conducta inapropiada, Spam, Ausencia injustificada) y escribir un comentario.
     * Confirmar la acción.
  3. El usuario queda bloqueado: desaparece inmediatamente de tu lista de búsquedas y sugerencias.
  4. Si existía alguna propuesta de intercambio pendiente o recíproca con dicho usuario, el backend anula el match automáticamente para proteger a ambas partes.
