# Flauta: entrenar con articulaciones y visualizar los dedos

La captura y el validador usan **MediaPipe Hand Landmarker local** para estimar 21 articulaciones por mano. La digitación se aprende de las etiquetas del administrador; el detector preentrenado no conoce las notas de flauta. Ya no se usa la cuadrícula 8×12 para entrenar o inferir postura.

## Probar

1. Ejecutar `npm ci` y `npm run dev` en `frontend/`. El paso `predev` prepara el modelo y WASM. Reiniciar el backend actualizado.
2. Abrir captura, aceptar consentimiento y activar cámara. Sobre el video se dibujan articulaciones y conexiones; las puntas son blancas.
3. Marcar **boquilla y extremo inferior** del instrumento, en ese orden. Alternativamente, alinear físicamente la flauta con la línea amarilla y confirmar mediante el botón accesible por teclado. Mantener esa posición durante la toma.
4. Seleccionar etiquetas y participante estable, y volver a pulsar Grabar. Se guardan varios fotogramas sincronizados con audio, no solo uno central.
5. En el estudio, **Reutilizar videos guardados** permite reproducir, calibrar y reprocesar un video ya etiquetado, sin subirlo otra vez. Conserva participante, nota y etiquetas. Si faltan suficientes articulaciones, no sustituye las etiquetas anteriores.
6. Entrenar y activar una versión nueva. En el validador, calibrar nuevamente; la secuencia comienza después de detectar las manos necesarias y recibir la primera inferencia.

Los videos originales no se borran. Los videos sin etiquetas revisadas deben etiquetarse antes de reutilizarlos con este flujo. Las grabaciones no se envían a Google ni a una API externa para inferencia.

## Qué representan los datos

| Campo | Contrato |
|---|---|
| `visual_schema` | `hand-landmarks-flute-axis-v1` |
| Vector visual | 128 valores: dos slots según handedness del detector; presencia + 21 coordenadas xyz por slot |
| Coordenadas | x transversal y y longitudinal al eje calibrado; distancias divididas por longitud visible de flauta; z relativo a muñeca |
| Fotogramas por video | 3–120 pares audio/visual; se conserva el mismo participante para todos |
| Métricas | Aciertos y matriz por **fotograma**, no número de participantes independientes |
| Separación | Participantes disjuntos entre entrenamiento y prueba, incluyendo todos sus videos/fotogramas |

Las cuadrículas antiguas quedan excluidas; no se rellenan ni reinterpretan como articulaciones. Un modelo antiguo no puede activarse con este contrato y uno que ya estaba activo devuelve 409 al inferir. Es necesario reprocesar y reentrenar.

## Límites y resultados inconclusos

- La línea amarilla es **calibración manual**, no detección ni seguimiento automático de flauta/agujeros. Si el instrumento se mueve respecto de ella, hay que detener y recalibrar. No se garantiza invariancia frente a rotación fuera del plano.
- Las articulaciones son estimaciones: dedos ocultos y el pulgar trasero pueden no observarse correctamente. Puntos dibujados no prueban contacto con un agujero ni un sellado acústico.
- Falta de landmarks, baja confianza, clase no entrenada o modelo visual que no supera la línea base independiente producen `posture_ok: null`, no digitación incorrecta.
- El segmento necesita al menos tres inferencias evaluables y un 70% de observaciones evaluables. Si no, el total queda inconcluso y no se emite aprobado/reprobado.
- La cámara y el detector no se han validado aquí físicamente con personas y flauta. Las pruebas automatizadas de geometría, contratos y overlay no sustituyen esa validación.

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
npx vitest run src/test/flute-hand-features.test.ts src/test/flute-hand-overlay.test.tsx src/test/admin-dataset-capture-ui.test.tsx
npm run build
cd ../backend
.venv/bin/python -m pytest tests/test_flute_hand_landmarks.py -q
```
