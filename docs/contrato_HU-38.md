# HU-38 — Contrato funcional y técnico ratificado

**Estado:** contrato ratificado el 17/11/2026 e implementado para el alcance gratuito acordado; el cobro al superar cupos continúa condicionado por HU-42.
**Base:** rama `feat/hu-38-session-scheduling`, HU-38, RF-SES-02/03/06 y AGENTS.md. Validación técnica registrada el 18/11/2026.

## 0. Baseline técnico verificado

- La implementación partió de `origin/dev` en `0e17168`; la sincronización final con `dev` se realizará antes del Pull Request.
- Alembic quedó consolidado en un único head `aa38c7d9e102`, con migraciones HU-38 reversibles verificadas.
- `backend/app/services/session_service.py` pertenece a revocación/refresco JWT; HU-38 usará `exchange_session_service.py` para evitar colisión semántica.
- Existe `Wallet` con saldo inicial en cero, pero no existen `PointTransaction`, escrow ni operaciones de pago HU-42.
- Las preferencias `in_app`, `push` y `email`, el correo SMTP y Web Push web/PWA disponen de entrega programada mediante Celery. Push nativo Capacitor no forma parte de HU-38.
- Los tipos durables de notificación fueron ampliados para propuesta, aceptación, rechazo, reprogramación, cancelación y recordatorios.

## 1. Reglas explícitas del backlog

- Actor MEMBER con match confirmado.
- Sesión gratuita hasta 60 minutos.
- Máximo **2 sesiones gratuitas por persona por semana**.
- Descontar cupo al crear agenda (`POST /api/sessions`).
- Sin cupo, exigir pago en puntos.
- Cancelar con `cancellation_reason` obligatorio; restaurar cupo si válida y oportuna.
- Más de 3 cancelaciones al mes **o** sobre la hora → bloqueo de agendamiento 7 días.
- Endpoint productivo previo `GET /api/matches/{match_id}/session-options` y endpoints GET/POST `/api/sessions`, POST `/api/sessions/{id}/cancel`, PUT `/api/sessions/{id}/reschedule`, PATCH `/api/sessions/{id}/status`.
- GET listado con `count` y `free_sessions_left`.
- UI calendario, widget X/2, modal, Zustand, toasts y responsive.
- Vistas desktop 03B/03C/03D/20/21; mobile 05B/05C/05D/22/23.
- RF-SES-03 huecos comunes y RF-SES-06 recordatorios; alcance visual menciona Google Calendar.

## 2. Contrato de identidad y autorización

- JWT `get_current_user`; `UserRole.MEMBER` exclusivamente.
- Usuario debe ser miembro del `Match` **confirmado**; impedir agenda si existe bloqueo bilateral HU-26.
- Los dos participantes de la sesión se obtienen de `Match`; el cliente no puede sustituir IDs ajenos.
- La contraparte del proponente acepta/rechaza. Cualquiera de los participantes puede cancelar o proponer una reprogramación.
- No exponer sesiones de terceros; 404 para recurso no visible (propuesta; seguir convención actual).
- `User.is_locked` no equivale a sanción de agenda.

## 3. Endpoints y ejemplos de DTO

**Todos** retornan `{statuscode, message, data, count?}`; `count` en GET paginado.

### `GET /api/matches/{match_id}/session-options`

Contrato productivo de solo lectura que resuelve los identificadores autorizados y recomienda franjas comunes antes de `POST /api/sessions`. Requiere MEMBER participante y match `confirmed`; aplica 404 a terceros y 409 a matches no confirmados o participantes bloqueados. Calcula 14 días en bloques de 30/60 minutos considerando timezone, modalidad, disponibilidad, buffers y sesiones activas. No crea sesiones ni consume cupos.

```json
{
  "statuscode": 200,
  "message": "Opciones de agendamiento recuperadas exitosamente.",
  "data": {
    "match_id": "0f0d81a5-806c-4aa0-bf34-327195fa4d92",
    "timezone": "America/La_Paz",
    "horizon_days": 14,
    "booking_blocked_until": null,
    "directions": [
      {
        "instructor_id": "b274dc33-1d6a-4f83-b62b-58062eb6e6ad",
        "instructor_name": "Miembro instructor",
        "learner_id": "4ae67b9c-d17c-4385-a24c-f358cd399265",
        "teaching_skill_id": "6f21768b-b01e-4bbc-b1cc-82a29297bf41",
        "skill_name": "Python",
        "modalities": ["VIRTUAL"],
        "common_slots": [
          {
            "starts_at": "2026-11-20T18:00:00Z",
            "ends_at": "2026-11-20T19:00:00Z",
            "timezone": "America/La_Paz",
            "modality": "VIRTUAL",
            "duration_minutes": 60
          }
        ]
      }
    ]
  }
}
```

`booking_blocked_until` informa una sanción activa sin ocultar las opciones; `POST /api/sessions` continúa siendo la autoridad final y rechazará la creación mientras el bloqueo siga vigente.

### `GET /api/sessions?page=1&page_size=20&status=PENDING`

```json
{
  "statuscode": 200,
  "message": "Sesiones consultadas correctamente.",
  "data": {
    "items": [],
    "free_sessions_left": 2,
    "free_sessions_limit": 2,
    "week_start": "2026-11-16"
  },
  "count": 0
}
```

La estructura interna de `data` es propuesta; el `count` total es obligatorio según HU.

### `POST /api/sessions`

```json
{
  "match_id": "0f0d81a5-806c-4aa0-bf34-327195fa4d92",
  "teaching_skill_id": "6f21768b-b01e-4bbc-b1cc-82a29297bf41",
  "instructor_id": "b274dc33-1d6a-4f83-b62b-58062eb6e6ad",
  "starts_at": "2026-11-20T14:00:00Z",
  "ends_at": "2026-11-20T15:00:00Z",
  "timezone": "America/La_Paz",
  "modality": "VIRTUAL"
}
```

El aprendiz se deriva del `Match`; el cliente no envía un ID libre para sustituirlo. Validar match, habilidad propiedad del instructor, disponibilidad, conflicto, semana y cupo. Si no hay cupo, consultar HU-42 **antes** de confirmar reserva. Respuesta 201, `PENDING` con cuota reservada.

### `POST /api/sessions/{id}/cancel`

```json
{ "cancellation_reason": "Imprevisto familiar" }
```

Registrar actor, motivo, fecha, elegibilidad de restitución, sanción y evento auditado; idempotencia. `cancellation_reason` no puede ser vacío.

### `PUT /api/sessions/{id}/reschedule`

```json
{
  "starts_at": "2026-11-21T16:00:00Z",
  "ends_at": "2026-11-21T17:00:00Z"
}
```

Verificar conflictos, zona horaria y ajuste atómico de cupos entre semanas. **Propuesta:** reprogramación tras aceptación requiere nueva aceptación.

### `PATCH /api/sessions/{id}/status`

```json
{ "status": "ACCEPTED" }
```

Solo `ACCEPTED` o `REJECTED` por contraparte en HU-38; **no** permitir `COMPLETED` desde este endpoint (HU-39).

## 4. Estados propuestos

`PENDING` → `ACCEPTED` → `COMPLETED` (HU-39).
`PENDING` → `REJECTED`.
`PENDING`/`ACCEPTED` → `CANCELLED`.

Reprogramación: evento auditable; retorna a `PENDING` cuando cambia fecha/hora y requiere nueva aceptación de la contraparte. `COMPLETED` nunca se admite por el PATCH genérico.

## 5. Cuotas: propuesta de cálculo

- El cupo gratuito se consume al **aprendiz**; los roles pueden invertirse en otra sesión del mismo match.
- `week_start`: lunes 00:00 local del aprendiz; `week_end`: siguiente lunes 00:00. Los instantes se guardan en UTC.
- Descontar al POST, restaurar si rechazo o cancelación elegible, nunca dos veces.
- Si cambio de semana, liberar reserva anterior y reservar nueva en una transacción.
- Proteger carreras mediante lock por `user_id + week_start` y restricciones DB.
- Cuota de **2 sesiones**, no 120 minutos intercambiables: una sesión de 30 min consume 1 cupo, salvo regla contraria aprobada.

## 6. Cancelaciones y sanción — decisión de trabajo ratificada

- `cancellation_reason` es obligatorio, recortado y de 10 a 500 caracteres; no se clasifica semánticamente.
- Una cancelación es oportuna cuando ocurre al menos 24 horas antes de `starts_at`.
- “Sobre la hora” significa menos de 24 horas antes del inicio.
- Cualquiera de los participantes puede cancelar; la cancelación se atribuye al actor autenticado.
- Una cancelación oportuna restaura el cupo del aprendiz exactamente una vez. Una tardía no lo restaura.
- Cada cancelación cuenta para el actor en su mes calendario local. “Más de 3” activa el bloqueo desde la cuarta.
- Una sola cancelación sobre la hora activa el bloqueo por la alternativa “o” expresada en la HU.
- El bloqueo inicia en `cancelled_at` y dura siete días; no acorta un bloqueo vigente mayor.
- El bloqueo impide crear/proponer nuevas sesiones, no autenticarse, leer ni cancelar sesiones existentes.
- Persistir actor, motivo, instante, oportunidad, restitución y sanción en eventos inmutables.

## 7. Disponibilidad y conflictos

Usar `UserAvailability`, `User.timezone` y `buffer_minutes`. Validar coincidencia para ambos; sesiones no terminales deben excluirse de huecos comunes. Una sesión concreta solo admite `VIRTUAL` o `PRESENCIAL`; `BOTH` se limita a preferencias. No modificar disponibilidad recurrente al reservar.

Todas las sesiones de HU-38 duran entre 1 y 60 minutos, gratuitas o pagadas, hasta que otra historia apruebe una duración diferente.

## 8. Contrato HU-42

HU-38 necesita una interfaz estable:

```python
async def quote_session(session_context): ...
async def reserve_session_points(session_id, payer_id, tutor_id, amount, idempotency_key): ...
async def refund_session_points(session_id, reason, event_id): ...
```

**Firmas propuestas, no existentes.** La billetera actual no implementa transacciones ni escrow. Puede avanzarse con el flujo gratuito y la interfaz de integración, pero HU-38 no se declarará cerrada ni presentará sesiones pagadas como funcionales hasta integrar HU-42.

## 9. Recordatorios y calendario

**Decisión de trabajo ratificada el 18/11/2026:**

- Programar mediante Celery recordatorios a 24 horas y 1 hora antes de sesiones `ACCEPTED`.
- La entrega actual emite el recordatorio durable `SESSION_REMINDER` en la bandeja in-app y lo publica por el WebSocket existente cuando el usuario está conectado.
- Cada recordatorio debe ser idempotente por sesión, destinatario y umbral. Una cancelación, rechazo o reprogramación invalida el horario anterior; los reintentos nunca pueden duplicar el aviso.
- La entrega actual implementa exportación de una sesión aceptada como `.ics` y un enlace manual para añadirla a Google Calendar.
- El contrato HTTP será `GET /api/sessions/{session_id}/calendar-export`, protegido para participantes y disponible solo en estado `ACCEPTED`. Conserva el sobre `APIResponse` y devuelve en `data` el nombre del archivo, MIME, contenido iCalendar y URL manual de Google Calendar.
- Correo SMTP y Web Push web/PWA están implementados mediante Celery, Service Worker, VAPID, suscripciones por dispositivo y auditoría idempotente. El QA HTTPS real fue aprobado el 18/11/2026. La sincronización bidireccional con Google Calendar continúa aplazada.
- El push nativo de Capacitor mediante FCM/APNs queda explícitamente fuera de HU-38 y requiere una ampliación independiente.
- El OAuth de inicio de sesión no se reutiliza para Calendar. No se solicitan scopes de Calendar ni se almacenan refresh tokens hasta disponer de consentimiento específico, cifrado y revocación.
- La exportación manual no debe presentarse como sincronización automática.

## 10. Ratificación

- [x] Decisiones de trabajo ratificadas en conjunto.
- [x] El flujo gratuito puede avanzar sin presentar HU-38 como cerrada hasta integrar HU-42.
- [x] RF-SES-06 incluye recordatorios programados in-app, WebSocket y correo SMTP; se autoriza completar Web Push exclusivamente para navegador/PWA.
- [x] Push nativo Capacitor/FCM/APNs queda fuera del contrato HU-38.
- [x] Para esta entrega, RF-SES-15 se cubre parcialmente mediante `.ics` y enlace manual; la sincronización bidireccional permanece aplazada.
- [x] No reutilizar el token de login Google ni almacenar refresh tokens de Calendar.

**Resultado vigente:** Web Push web/PWA, Service Worker, VAPID, suscripciones por dispositivo y entrega Celery auditable quedaron implementados y validados. No se simulan cobros, escrow, push nativo Capacitor ni sincronización Calendar externa.
