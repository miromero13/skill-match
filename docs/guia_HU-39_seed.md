# HU-39 — Guía de Ejecución de Semilla (Seed) y Pruebas Visuales

Esta guía detalla cómo ejecutar la semilla de datos de **HU-39 ("Confirmación y Cierre de Sesión de Intercambio")**, cómo autenticarse de forma inmediata en el frontend sin depender de Google OAuth y cómo validar visual y funcionalmente cada escenario del ciclo de vida post-sesión.

---

## 1. Propósito y Características del Semillero

El script determinista [`backend/scripts/seed_hu39_qa.py`](file:///e:/Proyectos/Software1/skill-match/backend/scripts/seed_hu39_qa.py) genera un entorno quirúrgico y reproducible para pruebas de desarrollo y control de calidad (QA).

### Principales atributos:
- **Zero Third-Party LLM:** Cumple estrictamente con la política de no invocar modelos comerciales en la nube.
- **Identificadores deterministas:** Usuarios, habilidades, matches y sesiones poseen UUIDs fijos para facilitar la trazabilidad.
- **Tokens JWT válidos:** Genera credenciales de acceso con rol `MEMBER` listas para inyectarse en el `localStorage` del frontend.
- **Limpieza reversible (`--cleanup`):** Permite borrar exclusivamente los datos de prueba sin afectar usuarios ni configuraciones previas del sistema.

---

## 2. Requisitos Previos

Antes de ejecutar la semilla, asegúrate de tener:
1. **PostgreSQL** activo y con las migraciones al día (`alembic upgrade head`). La última revisión canónica debe ser `d49e1f5a8b72`.
2. **Backend FastAPI** en ejecución en el puerto `8000`:
   ```powershell
   cd backend
   .venv\Scripts\Activate.ps1
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```
3. **Frontend React** en ejecución en el puerto `5173`:
   ```cmd
   cd frontend
   npm run dev
   ```
4. **Variable de entorno en `frontend/.env`:**
   Asegúrate de que `VITE_API_URL` apunte al backend local:
   ```env
   VITE_API_URL="http://localhost:8000/api"
   ```

---

## 3. Ejecución de la Semilla

### 3.1 Sembrar datos de prueba
Abre una terminal en la carpeta raíz del proyecto y ejecuta:

```powershell
cd backend
.venv\Scripts\python.exe scripts/seed_hu39_qa.py
```

*Nota: La ejecución limpia automáticamente ejecuciones previas de HU-39 antes de sembrar, garantizando siempre un estado limpio y predecible.*

### 3.2 Limpieza quirúrgica de datos
Si deseas eliminar todos los datos de prueba generados por HU-39 sin tocar otras entidades de la base de datos, ejecuta:

```powershell
cd backend
.venv\Scripts\python.exe scripts/seed_hu39_qa.py --cleanup
```

---

## 4. Usuarios de Prueba y Acceso Rápido al Frontend

Dado que los miembros regulares utilizan autenticación exclusiva con Google, la semilla proporciona snippets JavaScript para iniciar sesión al instante pegándolos en la consola de desarrollador del navegador (**F12 → pestaña *Console***) estando en [http://localhost:5173](http://localhost:5173).

### 4.1 Usuario 1: Carlos Gómez (Aprendiz)
- **Email:** `carlos.aprendiz.hu39@skillmatch.io`
- **Rol:** `MEMBER`
- **PIN presencial:** se muestra en la salida del semillero y en el diálogo autorizado.
- **Snippet para iniciar sesión en la consola:**
```javascript
localStorage.setItem('skillmatch-auth-storage', JSON.stringify({"state": {"user": {"id": "a1111111-1111-4111-8111-111111111111", "email": "carlos.aprendiz.hu39@skillmatch.io", "fullName": "Carlos Gómez (Aprendiz)", "role": "MEMBER", "skillPointsBalance": 10, "reputationScore": 5.0, "trustLevel": 5, "isVerified": true}, "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhMTExMTExMS0xMTExLTQxMTEtODExMS0xMTExMTExMTExMTEiLCJyb2xlIjoiTUVNQkVSIiwiZXhwIjoxODI2NTk4NjA5LCJpYXQiOjE3OTUwNjI2MDksImp0aSI6IjM2YmFlY2FhLTA3NjktNGVkNi05ZjBjLTAyNWJiOTc1MWVlMSIsInR5cGUiOiJhY2Nlc3MifQ.blZJ71tUSWBt18wpR9ivw6b7r3eo_FuGNf83PEA7soc", "refreshToken": null, "isAuthenticated": true, "isLoading": false}, "version": 0})); window.location.href = '/app/sessions';
```

---

### 4.2 Usuario 2: Ana Martínez (Instructora)
- **Email:** `ana.instructora.hu39@skillmatch.io`
- **Rol:** `MEMBER`
- **PIN presencial:** se muestra en la salida del semillero y en el diálogo autorizado.
- **Snippet para iniciar sesión en la consola:**
```javascript
localStorage.setItem('skillmatch-auth-storage', JSON.stringify({"state": {"user": {"id": "b2222222-2222-4222-8222-222222222222", "email": "ana.instructora.hu39@skillmatch.io", "fullName": "Ana Martínez (Instructora)", "role": "MEMBER", "skillPointsBalance": 10, "reputationScore": 5.0, "trustLevel": 5, "isVerified": true}, "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJiMjIyMjIyMi0yMjIyLTQyMjItODIyMi0yMjIyMjIyMjIyMjIiLCJyb2xlIjoiTUVNQkVSIiwiZXhwIjoxODI2NTk4NjEwLCJpYXQiOjE3OTUwNjI2MTAsImp0aSI6ImE2MTczNGU5LTQwMzQtNDNiYi05ZTEyLTM3ZDEyYzE4NjMwZCIsInR5cGUiOiJhY2Nlc3MifQ.-D9XoKH8exvWEqFGJ_6kCoj1gYwt17w7wyDvFf_cJzQ", "refreshToken": null, "isAuthenticated": true, "isLoading": false}, "version": 0})); window.location.href = '/app/sessions';
```

---

## 5. Matriz de Escenarios Sembrados y Pasos de Verificación

Al navegar a `/app/sessions` encontrarás seis tarjetas de sesión creadas para probar cada flujo de la especificación técnica:

| # | Sesión ID | Modalidad | Estado | Qué prueba |
| :--- | :--- | :--- | :--- | :--- |
| **1** | `11111111-...-0001` | Virtual | `ACCEPTED` (Finalizada) | 1ª Confirmación pendiente por ambas partes. |
| **2** | `22222222-...-0002` | Virtual | `ACCEPTED` (1 confirmación) | Espera de contraparte y cierre exitoso con 50 min. |
| **3** | `33333333-...-0003` | Presencial | `ACCEPTED` (Finalizada) | PIN presencial (4 dígitos) y confirmación mutua. |
| **4** | `44444444-...-0004` | Virtual | `ACCEPTED` (Finalizada) | Reporte formal de inasistencia (No-Show). |
| **5** | `55555555-...-0005` | Virtual | `COMPLETED` | Historial de sesiones completadas y pestaña "Completadas". |
| **6** | `66666666-...-0006` | Virtual | `ACCEPTED` (Futura) | Guardas temporales: no permite confirmar antes de `ends_at`. |

---

### Procedimiento de Prueba Paso a Paso

### Escenario 1: Registro de la 1ª Confirmación (Sesión 1)
1. Inicia sesión como **Carlos Gómez**.
2. Ubica la sesión `11111111-...-0001` en `/app/sessions`.
3. Haz clic en el botón **"Confirmar sesión"**.
4. En el modal Shadcn/ui:
   - Selecciona uno de los presets rápidos (`30m`, `45m` o `60m`) o escribe manualmente los minutos (entre 1 y 60).
   - Opcionalmente añade temas abordados (ej. *"Repaso de componentes"*).
   - Pulsa **"Confirmar intercambio"**.
5. **Resultado esperado:**
   - Se muestra un toast con el mensaje canónico retornado por el backend.
   - La tarjeta de Carlos pasa a mostrar la alerta amarilla: *"Has registrado tu confirmación. Esperando la confirmación de la contraparte para completarla."*
   - La sesión sigue en estado `ACCEPTED` hasta que la contraparte confirme.

---

### Escenario 2: Completado Mutuo de Sesión (Sesión 2)
1. **Desde la cuenta de Carlos:** Observa que la sesión `22222222-...-0002` ya tiene su confirmación registrada por **50 minutos** y muestra la alerta de espera.
2. Abre la consola y cambia de usuario pegando el snippet de **Ana Martínez**.
3. Como **Ana**, ubica la sesión `22222222-...-0002` y haz clic en **"Confirmar sesión"**.
4. **Prueba de concordancia exacta:**
   - Ingresa exactamente **`50`** minutos.
   - Pulsa **"Confirmar intercambio"**.
5. **Resultado esperado:**
   - Al coincidir ambas duraciones (50 min), el backend ejecuta el cierre atómico bajo `SELECT ... FOR UPDATE`.
   - La tarjeta se actualiza en tiempo real mostrando el badge verde esmeralda **"Completada"**.
   - Muestra la alerta de éxito: *"Sesión completada y confirmada por ambas partes. Duración efectiva: 50 minutos."*

> [!NOTE]
> **Prueba de error (Discordancia de minutos):** Si como Ana intentaras confirmar con un valor distinto (ej. `45` minutos), el backend responderá `409 Conflict` indicando que las duraciones declaradas no coinciden, preservando la sesión sin alterar.

---

### Escenario 3: Validación con PIN Presencial (Sesión 3)
1. Inicia sesión como **Carlos** y localiza la sesión `33333333-...-0003` (Modalidad: *Presencial*).
2. Haz clic en el botón **"Mi PIN presencial"**:
   - Se abrirá un modal centralizado mostrando su código de 4 dígitos: **`4829`**, junto con la fecha de expiración (+24 horas post `ends_at`).
3. Ahora haz clic en **"Confirmar sesión"**:
   - Observa que, al ser modalidad presencial, el formulario incluye obligatoriamente el campo *"PIN presencial de la contraparte"*.
   - Si intentas enviar sin PIN o con menos de 4 dígitos, el formulario valida localmente e impide el envío.
   - Si introduces un PIN erróneo (ej. `0000`), el backend rechazará el intento y registrará un intento fallido (bloqueándose tras 5 intentos).
   - Ingresa el PIN de Ana mostrado por el semillero o por su diálogo autorizado, selecciona los minutos y confirma.
4. Repite el proceso desde la cuenta de **Ana** usando el PIN de Carlos mostrado por el semillero o por su diálogo autorizado para cerrar la sesión presencial.

---

### Escenario 4: Reporte de Inasistencia / No-Show (Sesión 4)
1. Inicia sesión como **Carlos** o **Ana**.
2. Localiza la sesión `44444444-...-0004` y haz clic en el botón destructivo **"Reportar inasistencia"**.
3. En el modal:
   - Verifica la advertencia de acción auditable.
   - Comprueba la validación de longitud del motivo (debe tener entre 10 y 500 caracteres; el contador se actualiza en vivo).
   - Escribe un motivo válido (ej. *"Esperé 30 minutos en la sala virtual y la contraparte no se presentó ni respondió mensajes"*).
   - Haz clic en **"Confirmar reporte"**.
4. **Resultado esperado:**
   - Se genera el registro en la tabla `session_no_show_reports` con estado `PENDING_REPUTATION` (sin simular reducciones arbitrarias de puntaje, respetando la compuerta de HU-40).
   - El botón de reporte se deshabilita para evitar dobles envíos.

---

### Escenario 5: Pestaña "Completadas" e Historial (Sesión 5)
1. En la barra de filtros superior de `/app/sessions`, haz clic en la pestaña **"Completadas"**.
2. Observa la sesión `55555555-...-0005`:
   - Estado: `Completada` (Badge verde esmeralda).
   - Mensaje de confirmación: *"Sesión completada y confirmada por ambas partes. Duración efectiva: 60 minutos."*
   - Opciones operativas deshabilitadas (no permite cancelar, reprogramar ni duplicar confirmaciones).

---

### Escenario 6: Guardas Temporales (Sesión 6)
1. Revisa la sesión `66666666-...-0006` en la pestaña *"Confirmadas"*.
2. Al tratarse de una sesión programada a futuro (aún no ha ocurrido):
   - **No** muestra el botón *"Confirmar sesión"*.
   - **No** muestra el botón *"Reportar inasistencia"*.
   - Muestra únicamente la opción *"Exportar al calendario"* y *"Cancelar sesión"*.

---

## 6. Integración con HU-40 y HU-42 (Comportamiento de Adaptadores)

Durante las pruebas se evidencia el cumplimiento estricto de las reglas de negocio respecto a historias dependientes no implementadas:
- **HU-40 (Reputación):** El adapter [`session_reputation_adapter.py`](file:///e:/Proyectos/Software1/skill-match/backend/app/services/session_reputation_adapter.py) registra el no-show como `PENDING_REPUTATION` sin inventar fórmulas ni modificar el puntaje del perfil.
- **HU-42 (Escrow y Billetera):** El adapter [`session_escrow_adapter.py`](file:///e:/Proyectos/Software1/skill-match/backend/app/services/session_escrow_adapter.py) marca las sesiones gratuitas como `NOT_APPLICABLE` y las de pago como `PENDING_HU42`, garantizando que ninguna transacción ficticia de puntos ocurra.
