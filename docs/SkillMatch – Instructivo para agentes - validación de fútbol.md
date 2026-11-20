# SkillMatch – Instructivo para agentes: validación de fútbol con IA propia

Nov 15, 2026 · @Luis Gabriel Janco

Este documento es la instrucción de trabajo para los agentes de IA que desarrollarán la validación de habilidad de fútbol sobre el backend FastAPI y el frontend React que ya existen. Léelo completo antes de escribir código y trabaja por fases.

## 0. Cómo trabajar con este documento

- Implementa las fases de la sección 11 en orden. Cada fase termina con **Hecho cuando**; no pases a la siguiente sin cumplirlo y con las pruebas en verde.
- **Primero inspecciona el repositorio existente** (estructura, autenticación, base de datos, migraciones, estilo de código) y adáptate. Las rutas y nombres de este documento son propuestas; si el repo ya tiene una convención, gana la del repo.
- Si algo no está definido, elige la opción más simple, anótala en `docs/decisions.md` y continúa. Solo detente a preguntar en los casos de la sección 14.
- Todo umbral numérico de este documento es un **valor inicial**; debe vivir en configuración (sección 13), no en el código.

## 1. Objetivo

Validar el nivel de un usuario (Principiante, Intermedio, Avanzado, Experto) en control de balón mediante un reto de toques grabado con cámara y micrófono. Resultado: nivel, confianza del modelo, métricas, retroalimentación y sello de habilidad verificada, con supervisión antifraude.

## 2. Reglas innegociables

1. **Prohibido** usar APIs o modelos de IA de terceros (OpenAI, Anthropic, Google, etc.), LLM, transcripción de voz o modelos generativos. La retroalimentación se arma con plantillas.
2. **Prohibido** descargar modelos preentrenados, salvo aprobación escrita del equipo. Los modelos se entrenan con el dataset propio. Las librerías clásicas (OpenCV, librosa, SciPy, scikit-learn, PyTorch) sí están permitidas.
3. Solo librerías open source con licencia permisiva (MIT, BSD, Apache). **No usar Ultralytics YOLO** (AGPL) ni dependencias con licencias restrictivas sin consultar.
4. Todo el procesamiento corre en infraestructura propia; ningún video, audio ni dato de usuario sale hacia servicios externos.
5. Privacidad: consentimiento explícito antes de grabar, retención limitada (sección 13), acceso al video solo por URL firmada y con rol autorizado.
6. Reproducibilidad: semillas fijas, versiones de dependencias fijadas, cada resultado guarda la versión del modelo y de la configuración usadas.
7. Sin datos reales de personas en el repositorio. Las pruebas usan datos sintéticos.

## 3. Alcance del MVP

| Incluye | No incluye (por ahora) |
| --- | --- |
| Reto de toques/dominio con cámara fija | Conducción, pases, tiros, partidos |
| Verificación de ambiente, prueba de vida y calibración | Estimación de pose del cuerpo |
| Seguimiento del balón con visión clásica | Distinguir pierna derecha e izquierda |
| Fusión audio + video de cada toque | Procesamiento en el dispositivo (ONNX Runtime Web) |
| Retos dinámicos «el entrenador dice» | Escala en centímetros (se usa diámetros de balón) |
| Clasificador de nivel propio y puntaje de riesgo | Revisión humana avanzada (solo se marca el estado) |

## 4. Stack

| Capa | Tecnología |
| --- | --- |
| Backend (ya existe) | Python 3.11, FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL |
| Añadir | Celery + Redis (cola), MinIO (archivos, compatible con S3), `PyJWT` si no está |
| Visión | OpenCV, NumPy, PyAV o FFmpeg, `filterpy` |
| Audio | `librosa`, `soundfile`, SciPy, `torchaudio` |
| ML | PyTorch, scikit-learn, XGBoost, Optuna, Albumentations, MLflow, DVC |
| Inferencia | ONNX y ONNX Runtime (CPU) |
| Frontend (ya existe) | React, TypeScript, `getUserMedia`, `MediaRecorder`, Web Audio API, Page Visibility y Fullscreen API, canvas |
| Etiquetado | CVAT (balón y toques), Label Studio (nivel) |
| Calidad | pytest, ruff, mypy, Vitest o Jest, Playwright para el flujo del navegador |

## 5. Estructura propuesta

```
backend/app/
  football/
    api/          # routers REST y WebSocket
    models/       # tablas SQLAlchemy
    schemas/      # Pydantic
    services/     # sesión, retos, almacenamiento
    pipeline/     # ball_tracker, audio_events, touch_events,
                  # fusion, challenge_engine, features, scoring, fraud
    tasks.py      # tareas Celery
    config.py
ml/
  data/           # manifest, scripts de ingesta (sin datos reales en git)
  train/          # entrenamiento de cada modelo
  eval/           # informes de métricas
  export/         # exportación a ONNX
tests/football/   # unitarias y de integración
  synthetic/      # generador de video y audio sintéticos
frontend/src/features/football-validation/
  components/ hooks/ state/ api/
```

## 6. Modelo de datos

| Tabla | Campos principales |
| --- | --- |
| `validation_sessions` | id, user\_id, skill\_id, estado, semilla, plan\_firmado, creada\_en, finalizada\_en, version\_modelo, version\_config |
| `challenge_segments` | session\_id, indice, tipo (LOW, HIGH, SLOW, FAST), inicio\_servidor\_ms, duracion\_ms, cumplimiento, latencia\_reaccion\_ms |
| `evidence_files` | session\_id, tipo (video, audio), ruta\_minio, duracion\_s, fps, sha256, expira\_en |
| `detected_events` | session\_id, tipo (touch\_video, impact\_audio, touch\_fused), t\_ms, estado (confirmed, video\_only, audio\_only), confianza |
| `session_features` | session\_id, json de características |
| `validation_results` | session\_id, nivel, probabilidades, confianza, puntaje\_riesgo, requiere\_revision, retroalimentacion |
| `fraud_incidents` | session\_id, tipo, severidad, t\_ms, detalle |
| `dataset_samples` | id, ruta, participante\_id, nivel\_etiquetado, conteo\_manual, dispositivo, ruido, superficie, consentimiento, particion |
| `model_versions` | id, nombre, version, ruta\_onnx, metricas, activa |

Una migración de Alembic por cambio; nunca editar migraciones ya aplicadas.

## 7. Contratos de API

Todas las rutas llevan prefijo `/api/v1/football`, exigen JWT y comprueban que la sesión pertenece al usuario.

| Método y ruta | Función |
| --- | --- |
| `POST /sessions` | Crea la sesión. Devuelve `session_id`, `ws_url`, semilla y los intentos restantes. Respeta límite de intentos y periodo de enfriamiento |
| `WS /sessions/{id}/ws` | Servidor → cliente: `command` (indice, tipo, inicio\_servidor\_ms, duracion\_ms), `status`, `progress`, `result_ready`. Cliente → servidor: `client_event` (tab\_hidden, focus\_lost, fullscreen\_exit, con marca de tiempo), `ping` |
| `POST /sessions/{id}/env-check` | El cliente envía los resultados de la verificación de ambiente (luz, ruido, rostro, balón, conexión). El servidor decide si se puede continuar |
| `POST /sessions/{id}/liveness` | Resultado de la prueba de vida |
| `POST /sessions/{id}/calibration` | Marca de tiempo del toque de calibración en el cliente |
| `PUT /sessions/{id}/chunks/{n}` | Sube el fragmento n del video (con audio, cada \~5 s). Idempotente: repetir el mismo fragmento no duplica |
| `POST /sessions/{id}/finalize` | Cierra la grabación, verifica fragmentos completos y encola el procesamiento. Responde 202 |
| `GET /sessions/{id}` | Estado: created, env\_check, liveness, calibration, recording, uploading, processing, scored, needs\_review, failed |
| `GET /sessions/{id}/result` | Resultado final (abajo) |

**Resultado:** nivel, probabilidades por nivel, confianza, métricas (toques, racha, toques por minuto, altura media, regularidad, cumplimiento por tramo), coherencia audio-video, puntaje de riesgo, incidencias, retroalimentación (lista de fortalezas y mejoras), `requiere_revision`, versión del modelo.

Errores con el formato de error ya usado en el repo. Los endpoints de dataset (alta de muestras, etiquetas) son internos y exigen rol administrador.

## 8. Pipeline de procesamiento

Tarea Celery `process_session(session_id)` que ejecuta los módulos en este orden y guarda el resultado de cada uno. Cada módulo es una función pura, probada de forma aislada.

| Módulo | Entrada → salida | Notas de implementación |
| --- | --- | --- |
| `ball_tracker` | video → `BallTrack` (t\_ms, x, y, radio, confianza) | Sustracción de fondo (MOG2), círculos de Hough, filtro de Kalman, rellenar huecos de hasta 5 fotogramas. Normaliza la altura en diámetros de balón usando el radio mediano. Interfaz intercambiable para sumar luego una red tipo TrackNet |
| `touch_events` | `BallTrack` → candidatos a toque | Suavizar con Savitzky-Golay. Candidato = mínimo local de altura donde la velocidad vertical pasa de bajada a subida con cambio superior al umbral |
| `audio_events` | audio → impactos | Mono 48 kHz, espectrograma mel, flujo espectral, selección de picos con umbral adaptativo (mediana + k·MAD, banda \~200–4000 Hz). Mientras no exista el clasificador propio de golpes, usar esta heurística |
| `fusion` | eventos de video y audio + calibración → eventos fusionados | Estima el desfase con el toque de calibración. Empareja con tolerancia de ±70 ms: confirmed, video\_only, audio\_only. **Coherencia** = confirmados / total de eventos. **Deriva** = pendiente de la regresión del desfase en el tiempo (ms por minuto) |
| `challenge_engine` | plan + eventos fusionados → cumplimiento por tramo | LOW: altura mediana < 1,5 diámetros; HIGH: > 3; SLOW: intervalo mediano > 1,0 s; FAST: < 0,6 s. Puntaje 0 a 1 con tolerancia. Latencia de reacción = tiempo desde la orden hasta el primer cambio de comportamiento |
| `features` | todo lo anterior → dict de características | Toques totales, racha máxima, toques por minuto, regularidad (desviación de intervalos), altura media y variación, desplazamiento horizontal, caídas, cumplimiento medio, latencia media, tasa de confirmación, coherencia |
| `scoring` | características → nivel, probabilidades, confianza | Fase inicial: reglas con umbrales de configuración. Luego modelo entrenado (clasificación ordinal, probabilidades calibradas). Si la confianza es menor a 0,55, `requiere_revision` |
| `fraud` | señales → puntaje 0 a 100 + incidencias | Ver abajo |

**Generación del plan de retos (`challenge_engine.generate_plan`):** 4 a 6 tramos de 8 a 10 s, sin repetir el mismo tipo seguido, generados con la semilla del servidor y firmados con HMAC. El servidor emite cada orden por WebSocket y guarda su marca de tiempo real.

**Señales antifraude:** coherencia audio-video baja, deriva del desfase, cambios de pestaña o de foco, fotogramas repetidos o cortes (diferencia entre fotogramas y flujo óptico), cámara no fija, persona o balón fuera de cuadro, más de un rostro, latencia de reacción irreal (menor a 0,15 s o ausente), secuencia de órdenes que no coincide con el plan, metadatos inconsistentes (duración del video distinta a la sesión). Cada señal tiene severidad configurable; el riesgo es una combinación ponderada. Riesgo alto invalida o manda a revisión; nunca descarta en silencio.

## 9. Frontend

Módulo `football-validation` con una máquina de estados (por ejemplo con `useReducer`) que refleja los estados del servidor.

- **Pantallas:** intro y consentimiento, verificación de ambiente, prueba de vida, calibración, grabación con retos, subida y procesamiento, resultado. Sigue el diseño del brief del prototipo (pantallas D2 a D12).
- **Hooks:** `useMediaCapture`, `useChallengeSocket`, `usePageVisibility`, `useChunkUploader`.
- **Captura:** `getUserMedia` con `{ audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false, channelCount: 1, sampleRate: 48000 }, video: { width: 1280, height: 720, frameRate: { ideal: 30 } } }`. Grabar audio y video en el mismo `MediaRecorder` y fragmentar cada \~5 s.
- **Subida:** reintentos con retroceso exponencial; si se corta la conexión, reanudar desde el último fragmento confirmado.
- **Ambiente:** medir luz media con un canvas, nivel de ruido con `AnalyserNode`, rostro y balón con chequeos livianos; mostrar qué falla y cómo corregirlo.
- **Antifraude en cliente:** enviar por WebSocket cada cambio de pestaña, pérdida de foco o salida de pantalla completa.
- **UI de retos:** orden grande con cuenta regresiva, contador de toques en vivo (aproximado, no vinculante), banner de supervisión visible.
- **Resultado:** nivel, sello animado, métricas, retroalimentación, botón de revisión y de reintento con fecha.
- Compatible con el empaquetado móvil con Capacitor: pedir permisos de cámara y micrófono de forma explícita.

## 10. Datos y entrenamiento

**Formato del dataset:** `ml/data/manifest.csv` con `sample_id, path, participant_id, level_label, manual_touch_count, device, noise_level, surface, consent_id, split`. La partición se hace **por participante** (nunca por clip) para evitar fuga de datos.

**Etiquetado:** CVAT para el balón y los toques; Label Studio para el nivel, con dos evaluadores por clip. Guía de etiquetado:

- Toque = contacto del balón con cualquier parte del cuerpo que lo lance de nuevo hacia arriba.
- Caída = el balón toca el suelo o sale del cuadro.
- Se guarda el acuerdo entre evaluadores; las discrepancias se resuelven con un tercero.

**Rúbrica provisional de nivel** (hipótesis a calibrar con los evaluadores, no verdad): Principiante, racha máxima menor a 8; Intermedio, de 8 a 25; Avanzado, de 26 a 60; Experto, más de 60, combinado con cumplimiento de retos y regularidad.

**Modelos a entrenar** (cada uno con script en `ml/train/`, seguimiento en MLflow, exportación a ONNX y registro en `model_versions`):

1. Clasificador de golpes de audio (CNN pequeña sobre ventanas mel).
2. Validador de toques (gradient boosting sobre ventanas de trayectoria).
3. Clasificador de nivel (XGBoost o scikit-learn, validación cruzada agrupada por participante).
4. Modelo de riesgo de fraude (regresión logística o Isolation Forest sobre señales).
5. Opcional: red tipo TrackNet para el balón.

**Herramienta de captura de datos:** modo de desarrollo del frontend que graba el reto, pide el conteo manual y el consentimiento y sube la muestra al dataset. Es la primera prioridad porque la recolección es lo que más tarda.

Volumen orientativo: 200 a 300 clips de 30 s de 25 a 40 personas; 1500 a 3000 fotogramas con balón etiquetado; golpes de audio etiquetados incluyendo sonidos parecidos.

## 11. Fases y criterios de aceptación

| Fase | Tareas | Hecho cuando |
| --- | --- | --- |
| **0. Andamiaje** | Celery + Redis, MinIO, tablas y migraciones, router `football`, WebSocket base, CI con ruff, mypy y pytest | `POST /sessions` crea sesión, el WS conecta, una tarea Celery de prueba corre y la CI pasa |
| **1. Captura y subida** | Hooks de captura, grabación por fragmentos, `PUT /chunks`, `finalize`, estados de sesión, modo de captura de dataset | Un video de 40 s se sube por fragmentos, se reanuda tras cortar la red y queda ensamblado en MinIO con su hash |
| **2. Balón y toques por video** | `ball_tracker`, `touch_events`, generador sintético, script de evaluación contra conteo manual | En los videos sintéticos el conteo es exacto; en 20 clips reales error medio ≤ 2 toques |
| **3. Audio y fusión** | `audio_events`, calibración, `fusion`, coherencia y deriva | Fusión mejora la precisión del conteo frente a solo video, medida en el mismo conjunto; un video con audio desfasado o editado produce coherencia baja |
| **4. Retos dinámicos** | `generate_plan`, firma HMAC, órdenes por WS, UI de retos, `challenge_engine` | Un plan fijo produce cumplimiento correcto en sintéticos; un video grabado con otro plan queda marcado como incoherente |
| **5. Características, nivel y resultado** | `features`, `scoring` por reglas, `GET /result`, retroalimentación por plantillas, pantalla de resultado | El flujo completo funciona de extremo a extremo con el modelo de reglas y el resultado guarda versiones |
| **6. Antifraude** | `fraud`, incidencias, banner de supervisión, estados de revisión | Cada ataque simulado de la lista de pruebas dispara su incidencia; falsos positivos ≤ 5 % en clips legítimos |
| **7. Entrenamiento (en paralelo desde la fase 1)** | Recolección, etiquetado, entrenamiento, evaluación, exportación ONNX, activar modelos por versión | Los modelos entrenados superan a las reglas en el conjunto de prueba y se activan sin cambiar el código |
| **8. Cierre** | Prueba con personas nuevas, informe de métricas, documentación | Se cumplen las metas de la sección 12 |

## 12. Pruebas y métricas

- **Generador sintético** (`tests/football/synthetic`): con OpenCV dibuja un círculo que rebota con toques conocidos, fondo y ruido configurables, y genera un audio con clics en los mismos instantes (con desfase ajustable). Sirve para probar todo sin datos reales desde el primer día.
- **Pruebas unitarias** por módulo y de integración del pipeline completo; prueba de Playwright del flujo de captura con una cámara virtual.
- **Ataques simulados** para antifraude: video pregrabado, audio superpuesto, cortes, segunda persona, secuencia de retos equivocada, cambio de pestaña.
- `ml/eval/report.py` genera un informe con error del conteo, precisión y exhaustividad de toques (con y sin fusión), matriz de confusión del nivel, kappa ponderado y tasa de detección de fraude.

**Metas de aceptación (propuestas):**

| Métrica | Meta |
| --- | --- |
| Error de conteo de toques | ≤ 1 toque o ≤ 10 % |
| Precisión y exhaustividad de toques | ≥ 90 % |
| Nivel: acierto exacto / a ±1 nivel | ≥ 75 % / ≥ 90 % |
| Fraude simulado detectado | ≥ 90 % con falsos positivos ≤ 5 % |
| Tiempo de procesamiento de un clip de 60 s | ≤ 2 minutos en CPU |

La evaluación final se hace solo con participantes que no estuvieron en el entrenamiento.

## 13. Seguridad y configuración

- **Configuración** en `config.yaml` (con valores por entorno): todos los umbrales (tolerancia de fusión, 1,5 y 3 diámetros, 0,6 y 1,0 s, confianza mínima, pesos de riesgo, tamaño de fragmento, retención). Cada resultado guarda el hash de la configuración usada.
- **Autenticación y límites:** JWT, límite de intentos por habilidad con periodo de enfriamiento, límite de tasa en subidas.
- **Archivos:** URL firmadas de corta duración, verificación de tipo y tamaño, hash SHA-256 por fragmento.
- **Retención:** videos y audio se eliminan a los 30 días (configurable) salvo muestras de dataset con consentimiento; los resultados y métricas se conservan.
- **Registros:** logs estructurados con `session_id`, sin datos personales ni contenido multimedia.
- **Observabilidad:** tiempo por etapa del pipeline y tasa de fallos, para localizar cuellos de botella.

## 14. Convenciones y límites de los agentes

- Una rama por fase o tarea, commits pequeños, PR con descripción, pruebas y resultado del informe de métricas cuando aplique.
- Código con tipos, `ruff` y `mypy` limpios, funciones puras donde se pueda, sin números mágicos.
- No agregar dependencias sin justificarlas y comprobar su licencia.
- No subir videos, audios ni datos personales al repositorio.
- **Pregunta al humano antes de:** definir la rúbrica final de niveles, cambiar un umbral que afecte resultados, aceptar un modelo preentrenado de terceros, tocar el esquema de autenticación existente, o decidir cuánto tiempo se guardan los datos.
- Si una meta no se alcanza, informa la causa probable (datos, umbrales, ruido) en lugar de forzar el resultado.

## 15. Prompt de arranque para el agente

«Eres un ingeniero de software y ML. Lee completo el documento ‘SkillMatch – Instructivo para agentes: validación de fútbol con IA propia’. Primero inspecciona el repositorio existente (FastAPI y React) y resume su estructura, autenticación, base de datos y convenciones en `docs/repo-overview.md`. Luego implementa la Fase 0 respetando las reglas innegociables (sin IA de terceros, sin modelos preentrenados, solo librerías open source permisivas). Al terminar, ejecuta las pruebas, verifica el criterio ‘Hecho cuando’ y reporta qué se hizo, qué decisiones tomaste y qué necesitas del equipo antes de pasar a la Fase 1.»

Para cada fase siguiente, usa el mismo prompt cambiando el número de fase.
