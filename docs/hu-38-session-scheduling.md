# HU-38 — Agendamiento, cupos y cancelaciones

**Tareas ODD propuestas** para `odd/tasks/hu-38-session-scheduling.md`.
**Estado:** Checkpoints 0A, 1–5 y 7–9 completados; 0B, 6 y 10 parciales por regresión global heredada, E2E Celery SMTP, HU-42 y entrega Git pendientes.

## Checkpoints

- [x] 0A — Contrato ratificado.
- [ ] 0B — Baseline global parcial: regresión dirigida aprobada; suite global, lint, typecheck y build permanecen bloqueados por fallos heredados ajenos a HU-38.
- [x] 1 — Pruebas backend, PostgreSQL/API, estado frontend y UI escritas; backend rojo verificado.
- [x] 2 — Modelos y migración; merge de heads, reversibilidad y constraints validados.
- [x] 3 — Dominio y concurrencia.
- [x] 4 — API y Swagger.
- [x] 5 — Cupos, cancelaciones y sanciones.
- [ ] 6 — Integraciones parciales: in-app/WebSocket/correo, calendario manual y Web Push web/PWA con Celery implementados; QA Web Push HTTPS real aprobado, pendiente E2E Celery SMTP; push nativo Capacitor excluido.
- [x] 7 — Tipos, servicio API y Zustand.
- [x] 8 — UI responsive; flujo productivo y revisión visual móvil/tablet/desktop aprobados.
- [x] 9 — Integración real y QA: PostgreSQL, HTTP, OAuth, SMTP, calendario, responsive y Web Push HTTPS real aprobados.
- [ ] 10 — Regresión y cierre parcial: perímetro HU-38 verde y documentado; quedan bloqueos globales y PR.

## Preparación

- [x] Confirmar rama desde `origin/dev`, estado Git y cambios de compañeros (`0e17168`).
- [x] Leer AGENTS, arquitectura, HU-38, RF-SES-02/03/06 y código actualizado.
- [x] Ratificar `contrato_HU-38.md`: cupos, semana, cancelación, sanción, reprogramación y límites de pagos.
- [x] Delimitar HU-42 y responsabilidades RF-SES-06/15 como compuertas de cierre, sin simulaciones.
- [x] Capturar y actualizar baseline: los heads iniciales `f74e31b8a954` y `fcb6997ca958` fueron fusionados; Alembic validado con head único `aa38c7d9e102`.

## Tests primero

- [x] Tests de match confirmado, autenticación, pertenencia y aislamiento de terceros.
- [x] Tests de duración, modalidad, timezone, disponibilidad común y solapamientos.
- [x] Tests de cupo 2/semana, concurrencia sobre el último cupo y tercera sesión sin HU-42.
- [x] Tests de frontera 24 h, cuarta cancelación, restitución única y bloqueo 7 días.
- [x] Tests de reprogramación entre semanas y autorización de aceptación/rechazo.
- [x] Tests de bloqueos HU-26 y ausencia de pago HU-42.
- [x] Tests de rutas Swagger esperadas, `APIResponse`, listado, cupo y autorización.
- [x] Tests frontend de listado/cupo, creación, cancelación, doble envío, mensaje backend y descarte tras logout.

**Evidencia roja backend:** contratos/políticas `25 failed`; integración PostgreSQL/API `11 failed`, todos por rutas/schemas/políticas HU-38 todavía inexistentes. Ruff aprobado.
**Evidencia frontend:** dos archivos de pruebas escritos. Ejecución dirigida: 2 suites fallan antes de recolectar casos porque `node_modules` conserva una resolución incompleta de `dom-accessibility-api`; no es un fallo funcional HU-38.

## Backend

- [x] Diseñar modelo `ExchangeSession`, estados y auditoría.
- [x] Diseñar cuota semanal con invariantes transaccionales.
- [x] Crear merge de heads y migración Alembic funcional con constraints.
- [x] Implementar servicio de validación de match y participantes.
- [x] Implementar disponibilidad común y conflictos.
- [x] Implementar `GET /api/sessions` con `count` y cupos.
- [x] Implementar `POST /api/sessions` y reserva de cupo.
- [x] Implementar `PATCH /api/sessions/{id}/status`.
- [x] Implementar `PUT /api/sessions/{id}/reschedule`.
- [x] Implementar `POST /api/sessions/{id}/cancel` y auditoría.
- [x] Implementar sanción temporal de 7 días con reglas aprobadas.
- [ ] Integrar pago/escrow HU-42 (si disponible).
- [x] Ratificar recordatorios a 24 h y 1 h mediante Celery con entrega in-app/WebSocket e idempotencia durable.
- [x] Escribir pruebas de recordatorios, invalidación por cambios y ausencia de duplicados (`8 failed` rojos iniciales; Ruff aprobado).
- [x] Implementar políticas puras de recordatorios y emisiones determinísticas para ambos participantes (`8/8` pruebas nuevas verdes).
- [x] Implementar persistencia idempotente, Celery Beat cada cinco minutos, bandeja in-app y puente Redis post-commit hacia WebSocket.
- [x] Validar PostgreSQL real, reintento, reprogramación, estado terminal, tarea eager y migración reversible (`2 passed`; head `f38d5b7c8e93`).
- [x] Escribir primero los contratos de correo para plantilla, timezone, escape HTML, preferencias, identidad y errores SMTP (`9 failed` rojos iniciales).
- [x] Implementar transporte SMTP desacoplado, plantillas determinísticas y entrega persistida sin duplicados normales.
- [x] Validar PostgreSQL, cancelación previa al envío, reintento estable y migración reversible (`13 passed`; head `a38e7c9d1f04`).
- [x] Ejecutar una prueba controlada con Gmail SMTP y una contraseña de aplicación nueva; autenticación STARTTLS, envío y recepción aprobados sin guardar el secreto en Git.
- [ ] Validar E2E Celery con sesión `ACCEPTED`, preferencia email activa y segunda ejecución con cero reenvíos.
- [x] Ratificar Web Push exclusivamente para navegador/PWA mediante Service Worker y VAPID.
- [x] Excluir push nativo Capacitor mediante FCM/APNs como ampliación independiente.
- [x] Escribir pruebas de comportamiento para permisos, suscripciones, revocación, múltiples dispositivos, expiración e idempotencia; fase roja verificada (`20 failed` backend y `3 suites failed` frontend por módulos/rutas inexistentes).
- [x] Implementar políticas y schemas puros de Web Push: payload mínimo, identidad por evento/dispositivo, elegibilidad, clasificación HTTP, reintentos acotados y contratos estrictos (`17 passed`, `1 deselected`; Ruff aprobado).
- [x] Implementar configuración VAPID gobernada, persistencia y endpoints MEMBER protegidos (`20 passed`; Ruff aprobado; migración reversible; head `b38f6d7e8a90`).
- [x] Implementar Service Worker, registro/revocación explícitos desde Preferencias y apertura segura exclusiva de `/app/sessions` (`9 passed` Web Push; regresión dirigida `26 passed`; ESLint aprobado).
- [x] Integrar entrega Web Push con Celery, preferencias y auditoría idempotente por evento/dispositivo; procesar `404/410`, `429` y `5xx` (`23 passed`; Ruff y MyPy dirigidos aprobados; migración reversible; head `aa38c7d9e102`).
- [x] Generar y configurar un par VAPID exclusivo de desarrollo en almacenamiento ignorado; validar configuración, OpenAPI y ejecución Celery sin exponer secretos.
- [x] Ejecutar QA HTTPS Web Push en los navegadores disponibles: permiso, alta de suscripción, recepción, clic seguro hacia `/app/sessions`, ausencia de duplicados y revocación; validación manual aprobada por el usuario el 18/11/2026. Safari y push nativo Capacitor permanecen fuera del entorno disponible/alcance.
- [x] Ratificar exportación `.ics` y enlace manual a Google Calendar sin reutilizar OAuth de login.
- [x] Escribir pruebas contractuales de `.ics`, enlace Google y endpoint `APIResponse`.
- [x] Implementar generador `.ics`, enlace Google y endpoint backend protegido para sesiones aceptadas.
- [x] Conectar descarga `.ics` y enlace manual a Google Calendar en frontend para sesiones aceptadas.
- [x] Aplazar sincronización bidireccional, scopes Calendar y refresh tokens hasta disponer de cifrado y revocación.
- [x] Registrar router y documentar Swagger.
- [x] Implementar y documentar `GET /api/matches/{match_id}/session-options` como contrato productivo previo a la creación; 404 a terceros y franja consumible por POST probados con PostgreSQL real.
- [x] Ampliar notificaciones durables para propuesta, aceptación, rechazo, reprogramación y cancelación.
- [x] Verificar reintentos terminales sin notificaciones duplicadas.

## Frontend

- [x] Definir tipos, servicio API y store Zustand.
- [x] Probar las cinco operaciones, mensajes textuales, doble envío, carreras y logout (`12 passed`).
- [x] Vista de Mis Intercambios y agenda responsive.
- [x] Selector de horarios comunes con modalidad montado en el diálogo del match confirmado.
- [x] Widget “X/2” integrado en la vista de sesiones sin inventar un contador en Sidebar/Navbar.
- [x] Conectar la creación productiva a `session-options` usando IDs, timestamps, timezone y modalidad canónicos.
- [x] Aceptar, rechazar y reprogramar sesiones desde la vista productiva.
- [x] Modal de cancelación con motivo obligatorio de 10–500 caracteres.
- [x] Toast textual con `message` backend mediante servicio y store Zustand.
- [x] Carga, vacío, error, teclado y responsive por breakpoints; revisión visual móvil, tablet y desktop aprobada por el usuario.
- [x] Probar selector productivo, payload canónico y doble envío (`3 suites`, `9 tests passed`; ESLint dirigido aprobado).
- [x] Repetir revisión visual real del nuevo selector en móvil, tablet y desktop; aprobada por el usuario.

## Validación y entrega

- [x] Validar inicio de sesión MEMBER con Google OAuth real como prerrequisito del entorno (`/login` y `/api/health` HTTP 200; prueba manual aprobada el 18/11/2026).
- [x] Aprobar E2E transaccional PostgreSQL con dos participantes y tercero aislado (`test_hu38_e2e_qa.py`: `1 passed`).
- [x] Aprobar E2E HTTP real de 13 pasos, incluido `session-options`, cupos, HU-26, sanción e idempotencia (`run_hu38_e2e_live.py`).
- [x] Verificar limpieza automática acotada por UUID de todos los datos generados por QA.
- [x] Pruebas unitarias, integración y concurrencia PostgreSQL (41 aprobadas).
- [x] Pruebas de timezone/DST, cambios de semana y mes (suite dirigida ampliada a 46 aprobadas).
- [x] Regresión dirigida de matching, disponibilidad, bloqueos y notificaciones mediante E2E PostgreSQL/HTTP y suites específicas.
- [x] Regresión dirigida HU-38: backend `93 passed`, frontend `36 passed`, ESLint dirigido aprobado, OpenAPI con 90 rutas y Alembic en un único head `aa38c7d9e102` (18/11/2026).
- [x] Revisión visual responsive y contratos Swagger/OpenAPI del perímetro HU-38.
- [ ] Regresión global: backend recolecta 720 pruebas y obtuvo `698 passed / 21 failed / 1 skipped`; tres fallos horarios de HU-38 fueron corregidos y su perímetro volvió a `93 passed`, mientras los fallos globales restantes pertenecen a migraciones/auth/biometría/catálogo/matches/WebSocket y loops compartidos. Ruff global reporta 665 incidencias preexistentes. Frontend global obtuvo `187 passed / 7 failed`; lint y build/typecheck siguen bloqueados por deuda heredada y la instalación local incompleta de tipos de `lucide-react`.
- [x] Ignorar `backend/celerybeat-schedule` y sus variantes como artefactos runtime de Celery Beat.
- [x] Registrar limitaciones vigentes: HU-42, push nativo Capacitor, sincronización Calendar y ausencia de garantía exactly-once del protocolo SMTP.
- [ ] PR a `dev` según gobernanza; sin cambios directos a `main`.

## Definición de terminado

HU-38 completa **solo** si cumple los criterios explícitos de backlog, incluyendo pagos al superar cupos, sanciones, recordatorios y alcance visual acordado. Si falta HU-42 o sincronización exigida, documentar entrega parcial.
