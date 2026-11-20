# HU-38 — Agendamiento de sesiones: uso y pruebas

Esta guía permite al equipo levantar, probar y limpiar el escenario de la **HU-38: Agendamiento y ciclo de vida de sesiones de intercambio**. Complementa `backend/README.md` y no sustituye las migraciones ni los contratos Swagger.

## 1. Funcionalidades incluidas

- Consulta de habilidades, participantes, modalidades y franjas comunes mediante `GET /api/matches/{match_id}/session-options`.
- Creación de propuestas, control de dos sesiones gratuitas por semana y sesiones adicionales pagadas con SkillPoints mediante escrow HU-42.
- Aceptación, rechazo, reprogramación y cancelación justificada.
- Restitución de cupo y sanciones por cancelación tardía.
- Aislamiento `404` para terceros y bloqueo bilateral HU-26.
- Notificaciones durables y eventos WebSocket.
- Recordatorios internos, correo y Web Push web/PWA de 24 horas y 1 hora mediante Celery.
- Descarga `.ics` y enlace manual a Google Calendar para sesiones `ACCEPTED`.

No forman parte de esta entrega el push nativo Capacitor/FCM/APNs, OAuth de Calendar ni la sincronización bidireccional. El flujo pagado HU-42, correo y Web Push web/PWA están integrados; cada entorno debe aportar sus propias credenciales para los canales externos.

## 2. Requisitos previos

1. Configurar `backend/.env` a partir de `backend/env.template`.
2. Tener PostgreSQL accesible mediante la `DATABASE_URL` local.
3. Aplicar las migraciones vigentes.
4. Instalar las dependencias de backend y frontend.
5. Para recordatorios en tiempo real, disponer de Redis y ejecutar Celery worker y Beat.

Backend desde PowerShell:

```powershell
cd backend
.venv\Scripts\Activate.ps1
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend en otra terminal:

```powershell
cd frontend
npm install
npm run dev
```

Scheduler real, en terminales separadas desde `backend/`:

```powershell
celery -A app.core.celery_app.celery_app worker --loglevel=info
celery -A app.core.celery_app.celery_app beat --loglevel=info
```

Debe existir una sola instancia de Celery Beat. En pruebas automatizadas puede utilizarse `CELERY_TASK_ALWAYS_EAGER=True`.

### Configuración VAPID de desarrollo

Las claves se guardan en `backend/storage/vapid/`, ruta ignorada por Git. Para regenerarlas y configurar el `.env` local sin imprimir secretos:

```powershell
cd backend
New-Item -ItemType Directory -Force storage/vapid | Out-Null
Push-Location storage/vapid
..\..\.venv\Scripts\vapid.exe --gen --version2
Pop-Location
.venv\Scripts\python.exe scripts\configure_vapid_dev.py
```

Nunca copie `private_key.pem` al repositorio ni comparta su contenido. El par actual es exclusivamente local y debe sustituirse en staging/producción.

### Recorrido manual Web Push

1. Levantar PostgreSQL, Redis, backend, frontend, Celery worker y una sola instancia Beat.
2. Iniciar sesión como `MEMBER`; guardar el canal Push activo en Preferencias.
3. Pulsar **Activar notificaciones en este dispositivo** y conceder permiso sólo en ese momento.
4. Confirmar una sesión que entre en la ventana de 24 h o 1 h y ejecutar el barrido Celery.
5. Verificar una única notificación visible, hacer clic y confirmar navegación a `/app/sessions`.
6. Repetir el barrido y comprobar cero reenvíos para el mismo evento/dispositivo.
7. Revocar el dispositivo desde Preferencias y confirmar que deja de recibir avisos.
8. Repetir en Chrome, Edge y Firefox. `localhost` es un contexto seguro admitido por los navegadores para Service Worker; para un dominio remoto es obligatorio HTTPS con certificado confiable.

**Evidencia de cierre local (18/11/2026):** el usuario confirmó satisfactoriamente el recorrido Web Push sobre HTTPS local, incluyendo permiso concedido, Service Worker/suscripción activa, recepción del aviso, apertura segura de `/app/sessions` y control de duplicados/revocación en los navegadores disponibles. Safari y el push nativo Capacitor no formaron parte del entorno de QA disponible.

## 3. Semillero de QA

`backend/scripts/seed_hu38_qa.py` crea un escenario determinista en PostgreSQL. No es una migración Alembic y no debe ejecutarse en producción.

| Elemento | Identificador estable |
|---|---|
| Usuario A, aprendiz | `learner-hu38-qa@skillmatch.io` |
| Usuario B, instructor | `instructor-hu38-qa@skillmatch.io` |
| Usuario C, tercero | `outsider-hu38-qa@skillmatch.io` |
| Categoría | `cat-hu38-qa-deterministic` |
| Habilidad | `skill-hu38-qa-deterministic` |
| Match confirmado | `77777777-7777-4777-8777-777777777777` |

También crea habilidades de enseñanza/aprendizaje, disponibilidades comunes, preferencias de notificación y billeteras requeridas por el flujo.

### Cargar o restaurar el escenario

```powershell
cd backend
.venv\Scripts\python.exe scripts/seed_hu38_qa.py
```

La operación es idempotente: limpia exclusivamente el escenario identificado de HU-38 y vuelve a crearlo. Al finalizar imprime UUID, tokens JWT y snippets de inicio de sesión para los usuarios A y B, además de ejemplos `curl`.

Los tokens y snippets deben copiarse desde la salida de cada ejecución. No se guardan tokens estáticos en este README porque pueden caducar o no corresponder al `SECRET_KEY` local.

### Limpiar los datos

```powershell
cd backend
.venv\Scripts\python.exe scripts/seed_hu38_qa.py --cleanup
```

La limpieza usa IDs, correos y slugs deterministas. No ejecuta `TRUNCATE`, no elimina tokens revocados globales y no debe afectar usuarios ajenos a HU-38.

> El script se niega a ejecutarse si `ENVIRONMENT` indica `production` o `prod`. Comprueba siempre que `DATABASE_URL` apunte a una base local o de QA.

## 4. Prueba visual con dos usuarios

1. Ejecutar el semillero y conservar su salida.
2. Abrir `http://localhost:5173`.
3. Abrir DevTools y pegar el snippet de **Usuario A** impreso por el script.
4. Ir a Matches, abrir el match confirmado y proponer una sesión desde una franja disponible.
5. En otra ventana o perfil del navegador, pegar el snippet de **Usuario B**.
6. Entrar a `/app/sessions`, aceptar la propuesta y comprobar el estado `ACCEPTED`.
7. Probar reprogramación, rechazo y cancelación con motivo.
8. En una sesión aceptada, abrir **Añadir al calendario**:
   - descargar y abrir el archivo `.ics`;
   - abrir Google Calendar y comprobar el evento antes de guardarlo.
9. Usar el token del **Usuario C** impreso por el script para verificar que recursos ajenos respondan `404`, nunca `403`.

Repetir el flujo de sesiones y calendario en móvil, tablet y desktop para revisar responsividad.

## 5. Pruebas automatizadas

### Backend con PostgreSQL

```powershell
cd backend
.venv\Scripts\python.exe -m pytest `
  tests/test_hu38_e2e_qa.py `
  tests/test_exchange_sessions_behavior.py `
  tests/test_exchange_session_persistence.py `
  tests/test_exchange_sessions_db_behavior.py `
  tests/test_session_reminder_email_behavior.py `
  tests/test_session_reminders_calendar_behavior.py -v
```

### E2E contra el servidor HTTP local

Con el backend activo en `http://127.0.0.1:8000`:

```powershell
cd backend
.venv\Scripts\python.exe scripts/run_hu38_e2e_live.py
```

Este ejecutor crea y elimina sus propios datos; no requiere el semillero visual.

### Frontend

```powershell
cd frontend
npx vitest run `
  src/test/exchange-session-contract.test.ts `
  src/test/exchange-session-service.test.ts `
  src/test/exchange-session-ui.test.tsx `
  src/test/match-session-booking.test.tsx `
  src/test/match-session-options-service.test.ts `
  src/test/session-calendar-export.test.tsx
```

## 6. Contratos principales

- `GET /api/matches/{match_id}/session-options`
- `GET /api/sessions`
- `POST /api/sessions`
- `PATCH /api/sessions/{session_id}/status`
- `PUT /api/sessions/{session_id}/reschedule`
- `POST /api/sessions/{session_id}/cancel`
- `GET /api/sessions/{session_id}/calendar-export`

Todas las respuestas HTTP respetan `APIResponse`. Swagger está disponible con el backend activo en `http://127.0.0.1:8000/docs`.

## 7. Problemas frecuentes

- **`ERR_CONNECTION_REFUSED`:** el backend no está activo en el puerto 8000.
- **CORS desde `localhost:5173`:** comprobar la configuración local del backend y reiniciar el servidor.
- **JWT inválido:** volver a ejecutar el semillero y utilizar el snippet recién generado.
- **Error de configuración en `DEBUG`:** usar un booleano válido (`true` o `false`); valores como `release` impiden iniciar cualquier comando que cargue `Settings`.
- **No aparecen franjas:** volver a sembrar; las disponibilidades se calculan para el horizonte vigente.
- **No aparece calendario:** la acción solo está disponible para sesiones `ACCEPTED`.
- **No llegan recordatorios:** comprobar Redis, Celery worker, Celery Beat y preferencias.
- **La tercera sesión no se habilita:** la oferta debe aceptar puntos, tener una tarifa y el aprendiz debe disponer del saldo requerido; el frontend enviará `payment_method: "POINTS"` y el backend reservará la tarifa en escrow.

### Preparación local de Gmail SMTP

El entorno inicial de HU-38 puede utilizar una cuenta Gmail dedicada con `smtp.gmail.com:587` y STARTTLS. La cuenta debe tener verificación en dos pasos y una contraseña de aplicación vigente. La contraseña normal de Google no se utiliza.

```env
EMAIL_ENABLED=False
SMTP_HOST="smtp.gmail.com"
SMTP_PORT=587
SMTP_USERNAME=""
SMTP_PASSWORD=""
SMTP_STARTTLS=True
SMTP_TIMEOUT_SECONDS=15
EMAIL_FROM_ADDRESS=""
EMAIL_FROM_NAME="SkillMatch"
EMAIL_REPLY_TO=""
```

Las credenciales reales se guardan exclusivamente en `backend/.env`. Las pruebas automatizadas, el servicio SMTP y la integración persistida con Celery están implementados. La prueba aislada con Gmail real aprobó STARTTLS, autenticación, envío y recepción el 18/11/2026. Para habilitar el flujo programado, usar una contraseña de aplicación vigente, cambiar `EMAIL_ENABLED=True` y reiniciar worker y Beat. La autenticación SMTP no reutiliza el OAuth con el que los miembros inician sesión.

## 8. Cierre de las pruebas

```powershell
cd backend
.venv\Scripts\python.exe scripts/seed_hu38_qa.py --cleanup
```

No subas tokens, salidas del semillero, archivos `.env` ni credenciales personales al repositorio.
