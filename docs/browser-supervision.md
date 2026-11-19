# SM-43 — Prueba de supervisión del navegador

Esta prueba registra acciones reales del navegador en una bitácora propia. **No es un examen:** no modifica evaluaciones, `started_at`, cupos, notas ni certificados. No captura cámara, audio, texto del editor ni contenido del portapapeles. No aplica sanciones.

## Cómo probarlo en la aplicación

**Primero debe estar autorizada y aplicada la migración `bc43a710d962`.** No se aplicó sobre tu base durante este trabajo. Sin esas tablas, activar la sesión no funcionará; no hay bitácora ficticia de respaldo. No ejecutes seeds ni borres datos para preparar esta prueba.

1. Reiniciá el backend y recargá el frontend con los nuevos archivos. Iniciá sesión como MEMBER.
2. Abrí `/app/browser-supervision-test`. También hay un enlace **Probar controles del navegador (SM-43, sin examen)** en la preparación de una habilidad.
3. Leé las normas, marcá la aceptación y pulsá **Activar prueba**. La interfaz debe mostrar que es un ensayo sin consumo de intentos; el área de texto se habilita solo al confirmar el backend.
4. Ejecutá los casos de la tabla. Pulsá **Actualizar bitácora** para consultar lo confirmado por el servidor; **Cargar más incidentes** pagina el historial.
5. Pulsá **Cerrar prueba**: se detiene la captura, se confirman los pendientes y se cierra conservando la bitácora. Si no se pueden confirmar, se mantiene pausada y no se presenta un cierre exitoso.

| Acción real | Resultado esperado |
|---|---|
| Escribir y seleccionar texto dentro del área; copiar/cortar/pegar con teclado o menú | Bloqueo y aviso, sin guardar el contenido; un atajo no debe duplicarse por su evento de portapapeles |
| Copiar texto fuera del área | Portapapeles normal, sin incidente de copia |
| Arrastrar texto/archivo al área | No se inserta ni navega por ese drop; incidente `DROP` |
| Cambiar de pestaña o aplicación y volver | Una salida `AWAY` y un regreso `RETURN` con duración; blur+hidden no producen dos salidas |
| Entrar con el botón opcional a pantalla completa y salir con Escape | Incidente `FULLSCREEN_EXIT`; no se impide salir |
| Abrir la misma ruta en otra pestaña y activarla |409 del servidor y área deshabilitada mientras la primera conserva autorización |
| Recargar la pestaña | Bitácora consultable, área deshabilitada hasta reactivar; si la liberación no llegó, esperar hasta20segundos |
| Usar DevTools Network→Offline, generar una acción y volver a Online | Pendientes locales sin éxito ficticio; área pausada si no puede confirmar; renovación/reintento entrega los mismos UUID sin duplicar |
| Cerrar prueba y copiar/navegar normalmente | Controles desactivados; historial conservado |

Si el navegador interrumpe bruscamente la página, puede faltar `PAGE_EXIT`; no tomar su ausencia como prueba de continuidad. No borres almacenamiento del sitio si querés conservar incidentes no confirmados. El navegador puede limpiar su almacenamiento: la recuperación offline es best-effort, no un registro inviolable. No se puede impedir cerrar una pestaña o ventana.

En pantalla completa, Escape permite salir para volver a los botones. Si el navegador no soporta ese modo, informa el problema y la prueba puede continuar sin él. La política de este ensayo no implica que pantalla completa vaya a ser obligatoria en el examen futuro.

## Preparación y datos

La migración aditiva `bc43a710d962`, hija de `a732bd904c11`, agrega únicamente `browser_supervision_trials` y `browser_supervision_incidents`. No hay semillas, migraciones automáticas ni limpieza de registros existentes. La ejecución sobre la base de aplicación requiere autorización separada; mientras no se aplique, la prueba no puede persistir incidentes y no debe aparentar éxito.

Los ensayos duran como máximo24horas. Se conserva el historial al cerrar. Un miembro solo puede consultar sus propias sesiones; identificadores ajenos y usuarios ADMIN reciben404. No se ofrece endpoint de edición o borrado. El propietario de la base conserva acceso administrativo normal: esto no es una bitácora criptográficamente inviolable.

## Contrato de API

Todas las rutas usan `/api/browser-supervision/trials`, autenticación canónica y `APIResponse`. Los mensajes del servidor se muestran textualmente. Solo el listado incluye `count`.

| Método/ruta | Función |
|---|---|
| `POST /api/browser-supervision/trials` | `{tab_id: UUID, accepted: true}`; crea o recupera ensayo abierto y toma autorización de pestaña |
| `GET /{id}` | Consulta propia sin activar controles |
| `POST /{id}/heartbeat` | `{tab_id}`; renueva autorización |
| `POST /{id}/release` | Libera pestaña sin cerrar ni borrar |
| `POST /{id}/close` | Cierra ensayo conservando bitácora |
| `POST /{id}/events` | `{tab_id, events}`; lote atómico/idempotente |
| `GET /{id}/events?after=0&limit=50` | Secuencias posteriores a `after`, hasta200 filas y `count` total |

Un incidente contiene `event_id` UUID, `kind`, `observed_at` con zona horaria y `duration_ms` entero0–86400000. El servidor agrega `sequence` y `received_at`. Se rechazan campos extra, incluido contenido de portapapeles. Tipos: `AWAY`, `RETURN`, `COPY`, `CUT`, `PASTE`, `DROP`, `CONTEXT_MENU`, `FULLSCREEN_EXIT`, `OFFLINE`, `ONLINE`, `PAGE_EXIT`, `SESSION_OPEN`, `SESSION_RESUME`.

Cada lote contiene1–50 entradas. Un UUID repetido con idéntico contenido confirma el mismo incidente; con contenido diferente rechaza todo el lote409. Límites:200 incidentes nuevos/minuto y10000/ensayo; excederlos rechaza todo el lote429, sin agregar parcialmente ni incrementar contadores. Los duplicados exactos no consumen límites. Las horas del cliente son declaraciones no confiables; la hora de recepción es del servidor y no demuestra cuándo ocurrió un evento offline.

## Dos pestañas y recuperación

Solo una pestaña puede escribir por ensayo mediante una autorización de20segundos verificada en el servidor, con bloqueos de fila PostgreSQL. La vista renueva cada5segundos y deshabilita el área si no puede confirmar autorización. Una segunda pestaña puede consultar la bitácora, pero recibe409 al intentar activarse mientras la primera conserva autorización. Esto protege exclusivamente el ensayo, no implementa todavía el control de sesiones del examen SM-39.

Salir intenta liberar la autorización; una recarga o cierre abrupto puede no entregar esa solicitud. En ese caso se espera hasta20segundos antes de reactivar. No se promete detectar todos los cierres: el navegador puede terminar sin disparar eventos. La sesión no se cierra automáticamente por perder la conexión.

## Límites y alcance

SM-43 registra indicios; no certifica fraude. No puede identificar qué aplicación externa se abrió, ni detectar universalmente capturas de pantalla, ni controlar otro dispositivo, ni garantizar reportes de un cliente manipulado. Pérdidas de foco, pantalla completa o conectividad no son sanciones. Cámara, orientación del rostro y audio continuo pertenecen a SM-49.

La política de prueba bloquea portapapeles y arrastrar/soltar solo dentro del área supervisada. Pantalla completa es opcional y se solicita mediante acción explícita; escapar no queda atrapado. Los controles se quitan al salir. La cola del navegador se limita a500 incidentes y avisa ante desbordamiento, almacenamiento no disponible o errores; no guarda texto privado.

## Evidencia

- RED inicial:6 contratos HTTP fallaron por ausencia de endpoints (job23, pytest1), migración0, base descartable eliminada.
- GREEN backend:22 pruebas de trial/preflight/calibración (job24);7 de trial/concurrencia (job25), con conexiones independientes para reclamar simultáneamente y reenviar un incidente. Migración0/pytest0, base descartable eliminada. También se agregaron límites10000/ensayo, aceptación y expiración para la regresión final.
- GREEN frontend:19 pruebas de monitor/cola/vista/preflight y build TypeScript/Vite0. Primer typecheck detectó parameter properties incompatibles con erasableSyntaxOnly; corregido con campos explícitos. Un test de renovación instalaba fake timers después de crear el intervalo; corregido el harness sin debilitar el control.
- Regresión frontend completa (job27):194 pasan/1 falla en `evidence-navigation.test.tsx:149`, mismo caso previo de actualización de catálogo; no se modificó ni se autorizó repararlo. No se declara suite verde. Advertencia de build por chunk>500kB se mantiene.
- Regresión backend completa (job26):679 pasan/1 omitida por Garage S3/1 advertencia Starlette-httpx; migración0/pytest0, base descartable eliminada y base de aplicación intacta. Incluye el límite10000/ensayo, aceptación/expiración, competencia real entre conexiones y regresión previa.
- Recorrido físico pendiente. Pruebas de navegador automatizadas usan eventos sintéticos para políticas, no demuestran todos los comportamientos de un navegador/dispositivo real.
- Revisión independiente no disponible: el usuario pidió ejecución sin subagentes. No presentar el ensayo como certificado o listo para producción.
