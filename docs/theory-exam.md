# SM-39: banco de preguntas y examen oral

SM-39 está en implementación. El banco administrativo, el flujo oral y los adaptadores Gemini/OpenAI de texto están implementados parcialmente. El inicio permanece bloqueado hasta validar el ASR local; no se declara SM-39 listo para uso.

## Banco administrativo — primera unidad

Acceso exclusivo ADMIN, con sesión administrativa existente. MEMBER y visitantes reciben404 (`Recurso no encontrado`), sin revelar el contenido del banco.

| Operación | Ruta de esta unidad |
|---|---|
| Crear borrador | `POST /api/admin/theory/questions` |
| Listar borradores | `GET /api/admin/theory/questions` |
| Consultar última versión | `GET /api/admin/theory/questions/{id}` |

Filtros: `skill_id`, `level_number` (1–5), `status`; paginación con `offset` (desde0) y `limit` (1–100, por defecto20). `count` representa el total filtrado antes de paginar, no el tamaño de la página. No se incluye `count` en respuestas individuales ni errores.

El borrador requiere una habilidad/nivel existentes y un enunciado no vacío. Puede completarse después: una referencia vacía no autoriza su publicación ni permite usarlo en un examen.

```json
{
  "skill_id": "<UUID de una habilidad existente>",
  "level_number": 1,
  "kind": "OPEN",
  "prompt": "Explicá la diferencia de mutabilidad entre listas y tuplas.",
  "reference_answer": "Las listas son mutables; las tuplas son inmutables.",
  "criteria": [
    {"name": "Mutabilidad", "weight": 100, "description": "Distingue ambas estructuras y explica la posibilidad de modificación."}
  ],
  "time_limit_seconds": 90,
  "max_score": 20
}
```

Tipos previstos: `OPEN`, `MULTIPLE_CHOICE`, `TRUE_FALSE`. Opciones en `choices`: objetos con `code` y `text`; elección correcta en `correct_choice`. El contenido/rúbrica se devuelve únicamente al ADMIN, nunca mediante endpoints de miembros. Cada fila tiene ID y versión; las unidades siguientes habilitarán revisiones/publicación/archivo sin cambiar versiones usadas por exámenes anteriores.

## Base de datos y ejecución

La migración aditiva `c139a820f174`, posterior a `bc43a710d962`, se preparó y comprobó en una base descartable. No se ejecuta automáticamente en tu base ni se insertan preguntas de ejemplo al arrancar. No hay endpoint de borrado en esta unidad.

Verificación aislada desde `backend/`:

```bash
.venv/bin/python .venv/run_suite_hardening.py tests/test_theory_question_bank.py
```

El runner copia el proyecto, migra una base temporal, ejecuta las pruebas y elimina esa base. Conserva los datos de la aplicación y publica códigos de salida separados de migración/pytest.

Comprobación observada: RED11 por endpoints ausentes (job32, pytest1), luego35 pruebas correctas de banco/preflight/calibración/catálogo (job33, migración0/pytest0); bases descartables eliminadas. Son pruebas ejecutadas por el implementador, no revisión independiente.

## Estado actual

El banco administrativo, sus revisiones, la pantalla y el inicio atómico ya tienen implementación y pruebas. El estado histórico de esta sección precede a las unidades posteriores; el flujo oral, captura y adaptadores de corrección se implementaron después. No se incorporaron dependencias. El uso del corrector requiere configuración y consentimiento de texto explícito.


## Publicación y revisiones

- `PATCH /api/admin/theory/questions/{id}` recibe `expected_version` y `content` completo; crea una nueva revisión DRAFT, nunca modifica la anterior.
- `POST /api/admin/theory/questions/{id}/publish` recibe `expected_version`; requiere referencia no vacía, rúbrica con pesos que sumen100 y opciones coherentes con el tipo de pregunta.
- `POST /api/admin/theory/questions/{id}/archive` recibe `expected_version`; crea una revisión ARCHIVED, sin borrar historial.
- `GET /api/admin/theory/questions/{id}/versions` devuelve el historial con `count`.

Cada mutación bloquea una fila estable y compara la versión esperada; una versión obsoleta devuelve409 sin sobrescribir cambios. Publicar y archivar también crean versiones. Editar una pregunta publicada vuelve la última versión a borrador; el listado devuelve solo la última revisión por pregunta, filtrada por su estado actual. Los exámenes futuros conservarán su referencia a la versión asignada.

Para opción múltiple se requieren al menos dos códigos únicos y una elección correcta válida. Verdadero/falso exige códigos `TRUE` y `FALSE`. Una pregunta abierta no admite opciones ni elección correcta. Se permite guardar borradores incompletos, pero no publicarlos.


## Pantalla administrativa

Ruta `/admin/theory/questions`, enlace «Banco de Preguntas» del menú ADMIN. Permite filtrar por habilidad/nivel/estado, paginar, crear y editar borradores, publicar, archivar y consultar el historial. El formulario usa niveles del catálogo, respuesta de referencia, opciones y criterios ponderados. Cada publicación se valida en el servidor; sus mensajes y errores se muestran sin reemplazarlos por éxito simulado. La publicación no inicia ningún examen.

Antes de probarla con tu base debe aplicarse expresamente la migración del banco; esta implementación no la ejecuta sobre datos de aplicación. La pantalla administrativa no inicia el examen oral; el corrector textual se configura exclusivamente en el backend.


## Inicio real del examen

`POST /api/evaluations/start` recibe `evaluation_id`, `level_number` y `text_grading_consent`. Exige evaluación propia, consentimiento biométrico/calibración vigentes, consentimiento textual explícito, corrector backend configurado y al menos5 preguntas publicadas del nivel. Selecciona5 sin repetición, fija versiones/contenido de corrección y procedencia de proveedor/modelo/prompt, y fija un plazo global de10minutos. En la misma transacción registra `started_at`: a partir de ese punto el intento queda consumido, incluso si después se abandona.

Repetir la misma petición recupera el mismo inicio sin otro débito ni selección. Cambiar el nivel tras comenzar devuelve409. Las solicitudes se serializan por miembro para proteger también el cupo global entre habilidades. `GET /api/evaluations/{id}/questions` devuelve solo datos públicos: nunca respuesta de referencia, opción correcta ni rúbrica.

El consentimiento textual autoriza solo pregunta, referencia, rúbrica y transcripción; audio, video e identidad nunca se envían al proveedor. La negativa o falta de configuración ocurre antes de consumir el intento. El guard del ASR no validado permanece cerrado, por lo que el examen real no se puede completar todavía.

## Registro oral y plazos

`GET /api/evaluations/{id}/status` devuelve la pregunta activa y los plazos del servidor. Recargar no reinicia el tiempo. Las preguntas vencidas quedan como `TIMED_OUT`; terminar las ventanas lleva a `THEORY_PENDING_REVIEW`, sin inventar una nota.

`POST /api/evaluations/{id}/answers` recibe `submission_id`, `question_id` y `audio_base64`, no texto editable del cliente. Se guardan transcripción, digest y recepción, nunca el audio crudo. Repetir el mismo identificador y contenido devuelve el mismo recibo; un contenido distinto devuelve409. La inferencia ocurre fuera del bloqueo de base de datos y se revalida antes de persistir. El procesamiento tiene un timeout de60s y un máximo de dos inferencias nativas simultáneas; un hilo tardío no puede guardar respuestas.

## Transcripción local — candidato no aprobado

El adaptador usa el runtime Sherpa existente y Whisper multilingüe configurado en español. Los tres activos `encoder.onnx`, `decoder.onnx` y `tokens.txt` se provisionaron explícitamente solo en el worktree aislado, sin sobrescritura y con hashes verificados. No se descargan al atender peticiones. Ver [procedencia y resultado nativo](models/theory-whisper/README.md).

El candidato Tiny alteró una negación en la muestra sintética española: «las tuplas son inmutables» se transcribió como «las tuple son bien mutables». Por eso `APPROVED_FOR_EXAMS` permanece falso: disponer de archivos ejecutables no basta para habilitar certificaciones. No se validó eficacia con voz humana real.

Si faltan activos o el modelo no está aprobado, el inicio devuelve503 antes de consumir un intento. La transcripción también exige aprobación; una falla no registra una respuesta. El formato es WAV PCM mono de16kHz/16bits, con tamaño y duración acotados.

Las pruebas que sustituyen el transcriptor comprueban persistencia/idempotencia, no eficacia de reconocimiento. El corrector valida criterios exactos y el servidor calcula puntos ponderados de la rúbrica; fallo del proveedor deja corrección en error sin nota y permite reintento con procedencia fijada.

## Captura del navegador

El grabador de respuestas captura PCM real del micrófono, remuestrea a16kHz y produce WAV mono16bits. No usa almacenamiento persistente. Rechaza capturas vacías/no finitas, interrupciones del reloj y pérdida de la señal; el máximo por grabación es90s. Cancelar, abortar o detener libera tracks y nodos de audio. Si el permiso termina de concederse después de cancelar, el stream se libera sin activar la grabación. Es un componente de captura, no supervisión ni corrección de contenido.

Verificación del componente: ocho pruebas enfocadas de grabación/banco y TypeScript/Vite correctos (job56). La primera compilación detectó un tipo incorrecto en un mock (job55); se corrigió sin debilitar TypeScript. La prueba física del micrófono y la validación de fidelidad del reconocimiento siguen pendientes.

## Pantalla del miembro y recuperación

Ruta protegida `/evaluation/:id/theory`; la calibración exitosa ofrece «Continuar al examen oral». Abrir esa página no consume el intento: se requiere confirmar «Comenzar examen y consumir intento» y que todos los controles del servidor pasen. La vista no utiliza el layout demo ni simula supervisión continua.

La pantalla muestra pregunta/opciones, progreso y tiempo aproximado sincronizado con el servidor. La cámara se activa explícitamente como vista previa; el micrófono solo durante una respuesta. Salir, vencer la pregunta o perder la cámara cancela la grabación y libera recursos. El navegador muestra advertencia de salida cuando corresponde, sin prometer bloquear toda navegación.

Un fallo de red conserva el mismo audio/identificador en memoria para «Reenviar misma respuesta», sin duplicar el recibo. No se usa almacenamiento persistente para medios o transcripciones; salir pierde un envío pendiente. El intento iniciado no se devuelve. Al terminar se muestra el estado pendiente/error o el resultado con nota agregada y razones por criterio. No se otorga un sello ni certificado ficticio. La UI muestra los mensajes API textualmente.

## Estado de comprobaciones

- Backend antes del guard final de validación ASR:717 correctas/1 omitida por Garage S3/1 aviso Starlette-httpx (job53), migración0/pytest0 y base descartable eliminada.
- Captura/banco:8 enfocadas y TypeScript/Vite correctos (job56).
- Pantalla oral, grabación y compatibilidad de preembarque/calibración: pruebas enfocadas y build correctos (job58).
- Frontend completo después del flujo oral:209 correctas/1 fallo previo en `evidence-navigation.test.tsx:149` (job59), tests1/build0. Persiste advertencia de chunk>500kB.
- Prueba nativa sintética job62 ejecutó inferencia en0.523s pero falló en fidelidad semántica; su exit0 era solo un smoke test insuficiente, no aprobación del modelo.
- Guard de modelo no validado: RED job63 devolvía inicio200 indebidamente frente al503 esperado. GREEN job64:718 correctas/1 omitida Garage S3/1 aviso Starlette-httpx, migración0/pytest0 y base descartable eliminada. El modelo sigue deshabilitado para exámenes.
- Corrector Gemini/OpenAI: pruebas enfocadas T7 36 correctas, pantalla 5 correctas, build TypeScript/Vite correcto y suite frontend completa 211 correctas. La validación usa transporte HTTP simulado; no se llamaron proveedores reales.

La migración de consentimiento y procedencia/resultados se ejecutó únicamente en bases descartables del runner; no se migró ni escribió en la base de aplicación y no se insertaron preguntas. No se realizaron llamadas reales a Gemini/OpenAI. La validación funcional de proveedores usa transportes HTTP mock; no acredita eficacia del corrector ni reemplaza revisión independiente. El ASR sigue sin validación y bloquea el uso real de SM-39.
