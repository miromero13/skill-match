# Flauta: altura (pitch), dedos y evaluación

Pipeline de captura → entrenamiento → validador en vivo para flauta dulce soprano con **digitación alemana** (DO = C5 523,25 Hz … MI6 = E6 1318,5 Hz). Especificación y decisiones: [`odd/tasks/flute-pitch-fingering.md`](../odd/tasks/flute-pitch-fingering.md).

## Cómo decide

| Aspecto | Cómo se evalúa |
|---|---|
| Nota (sonido) | **La altura decide.** El navegador estima la frecuencia fundamental con YIN (430–1600 Hz) y el backend toma la nota más cercana, con ±60 cents de tolerancia, tras corregir la afinación del instrumento (`tuning_offset_cents`, mediana aprendida de las tomas etiquetadas, ±50 cents como máximo). |
| ¿Es flauta? | La cabeza MLP de sonido solo confirma flauta vs `NO_FLAUTA` (voz/ruido): `flute_probability = 1 − P(NO_FLAUTA) ≥ 0,5`. Silencio o altura fuera de tolerancia → `NO_FLAUTA`. |
| Postura | Cabeza multi-etiqueta que estima si cada uno de los **7 huecos frontales** está tapado. Las etiquetas salen de la tabla de digitación (`FRONT_HOLES`), así que cada toma correcta entrena todos los dedos. Cualquier hueco visto con seguridad en el estado incorrecto hace fallar la postura (las notas vecinas difieren en un solo dedo). Un hueco con probabilidad entre 0,35 y 0,65 es "incierto" y se tolera uno. |
| Pulgar trasero | No se ve en cámara: **no se evalúa**. DO6/RE6 y MI/MI6 tienen los mismos huecos frontales; los distingue el sonido. |
| Sin manos | No es una clase. Si faltan las manos requeridas, `posture_ok` es `null` (no evaluable). |

## Contrato de features

| Campo | Contrato |
|---|---|
| `audio_schema` | `flute-audio-pitch-v1`, 62 valores: `[0..47]` timbre (32 log-Mel, 13 MFCC, RMS, planitud, energía grave), `[48]` sonoro 0/1, `[49]` claridad YIN, `[50]` octavas sobre C5, `[51..61]` afinidad gaussiana (σ = 35 cents) a DO, RE, MI, FA, FA#, SOL, LA, SI, DO6, RE6, MI6 |
| `visual_schema` | `hand-landmarks-palm-v5`, 50 valores: 25 por mano (presencia, 5 flexiones, 5 distancias punta–palma, 5 punta–nudillo, 4 entre puntas, 5 alturas). Slot 0 = mano **izquierda real** del usuario: MediaPipe asume imagen espejada, así que se invierte su etiqueta de handedness |
| Fotogramas | 3–120 por toma. En tomas de flauta se descartan los fotogramas sin sonido; la toma se rechaza si menos del 30% de los fotogramas sonoros coincide con la nota etiquetada |

Los sidecars anteriores (audio de 48 valores, manos v4) se listan como `needs_reprocess`: se reprocesan desde **Reutilizar videos guardados**, sin regrabar. Un modelo de formato anterior devuelve 409 al activarse o inferir.

## Métricas de entrenamiento

- **Partición** (`split_mode`): `participant` (personas independientes, `validated: true`), si no `session` (mismo participante, otro día de captura), si no `take` (otras tomas de la misma sesión, optimista), si no `none` (experimental).
- **Unidad**: precisión por fotograma y **por toma** (`sample_test_accuracy`, voto mayoritario de los fotogramas de un video), con matriz de confusión por toma, precision/recall por clase y precisión por participante.
- **Dedos**: precisión por hueco frente a la línea base por mayoría, y porcentaje de tomas con la digitación completa reconocida.
- **Activación**: un modelo cuyo sonido no supera la línea base por mayoría en las tomas de prueba no se activa (409).
- **Ponderación**: cada toma pesa lo mismo, independientemente de cuántos fotogramas conserve.

## Validador en vivo

- **Examen**: se ignoran los primeros 400 ms de cada nota (ataque o transición) y el sonido se puntúa solo sobre fotogramas sonoros. El tiempo se mide con reloj real.
- **Modo libre** y **examen** usan la misma regla de postura del backend. La UI muestra qué hueco está mal o es incierto.

## Modo «Canción»

En el validador en vivo, «Canción» permite tocar una partitura completa (por ahora «Himno a la Alegría»: dos vueltas, 30 negras, 16 s a 120 BPM; la segunda vuelta termina Re, Do, Do). Especificación: [`odd/tasks/flute-song-mode.md`](../odd/tasks/flute-song-mode.md).

- **Flujo**: elegir canción y tempo (60–120 BPM) → cuenta de entrada de 4 clics → tocar sin clics → resultado nota por nota y Aprobado/Reprobado (≥ 80 %).
- **Captura**: el navegador mide la altura (YIN) cada 25 ms y timbre + manos cada 100 ms, y envía toda la interpretación a `POST /api/ai/datasets/samples/flute/score-song`. El catálogo sale de `GET /api/ai/datasets/samples/flute/songs` (definido en `backend/app/services/flute_song_service.py`).
- **Evaluación por nota**: la nota esperada debe dominar el 60 % central de su duración y entrar a ±150 ms. La latencia fija del micrófono se corrige con la primera nota tocada (−250…+500 ms; el ruido previo a la cuenta se ignora). En notas repetidas se exige el corte de aire («tu-tu»).
- **Sin modelo** se evalúa solo el sonido. Con modelo activo se suman la verificación «suena a flauta» y la digitación (25 %), solo en notas cuya digitación el modelo puede juzgar; si no, «no evaluable».
- Agregar una canción: sumar una entrada a `FLUTE_SONGS` (notas en tiempos de negra) y su imagen en `frontend/public/flute-songs/`.

## Límites

- Las articulaciones son estimaciones: dedos ocultos por la flauta pueden quedar inciertos. Ver un dedo cerca de un hueco no prueba que el hueco esté sellado.
- Con un solo participante, las métricas son intra-persona. La validación real requiere al menos 2–3 personas y 2 sesiones por persona.
- La cámara y el pitch no se validaron aquí físicamente con personas y flauta. Las pruebas automatizadas usan señales sintéticas.

## Inventario del detector auxiliar

| Componente | Versión / procedencia |
|---|---|
| Runtime | `@mediapipe/tasks-vision` 0.10.32, fijado en package-lock; proyecto MediaPipe, Apache-2.0 |
| Modelo | Hand Landmarker float16, versión 1, distribución oficial de MediaPipe |
| Fuente del modelo | https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task |
| SHA-256 | `fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1` |
| Documentación y términos | https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker y https://github.com/google-ai-edge/mediapipe/blob/master/LICENSE |
| Autorización | El solicitante autorizó incorporar el detector local en esta implementación tras explicar que era preentrenado; esto no sustituye una aprobación institucional/docente si corresponde |

`frontend/scripts/prepare-hand-assets.mjs` copia WASM desde la dependencia fijada y descarga el modelo únicamente si falta, verificando su hash. `predev` y `prebuild` lo ejecutan. La primera preparación requiere red; con el modelo presente no lo descarga de nuevo. Los assets generados se ignoran en Git y se incluyen en `dist` al compilar. No hay descargas a terceros durante la captura/prueba: el navegador carga los assets desde el mismo servidor de la aplicación.

## Verificación automatizada

```sh
cd frontend
npm run typecheck
npx vitest run src/test/flute- src/test/admin-dataset-capture-ui.test.tsx
cd ../backend
.venv/bin/python -m pytest tests/test_flute_training_service.py tests/test_flute_song_service.py tests/test_dataset_sample_model.py -q
```
