# SkillMatch — Registro de Decisiones Técnicas: Validación de Fútbol (`decisions.md`)

Este documento registra las decisiones de diseño e integración tomadas durante la implementación del sistema de validación de habilidad de fútbol con IA propia, siguiendo la regla de elegir la opción más simple y compatible con el repositorio existente.

---

## Fase 0 — Andamiaje

### D-01: Prefijo de rutas REST y WebSocket (`/api/football` y `/api/v1/football`)
- **Contexto:** El instructivo de fútbol propone el prefijo `/api/v1/football`, mientras que `AGENTS.md` (sección 3.1) establece rutas sin versionado bajo `/api/...` como convención del repositorio (`Si el repo ya tiene una convención, gana la del repo`).
- **Decisión:** Montar el router de fútbol tanto en `/api/football` (convención principal del repo) como en `/api/v1/football` (compatibilidad directa con el instructivo y clientes de prueba). Asimismo, las respuestas HTTP utilizan el sobre canónico `APIResponse[T]` (`statuscode`, `message`, `data`, `count`) del repositorio.

### D-02: Almacenamiento de objetos compatible con S3 mediante Garage S3 (Coolify VPS)
- **Contexto:** El equipo despliega **Garage S3** en un VPS propio administrado con Coolify en lugar de MinIO.
- **Decisión:** Implementar un servicio de almacenamiento S3 agnóstico del proveedor (`GarageS3StorageService` en `backend/app/football/services/storage.py`) usando `boto3` (licencia Apache 2.0, compatible con Garage S3 y firmas S3v4) configurado mediante variables `GARAGE_S3_*` (con retrocompatibilidad hacia `MINIO_*`). En entornos de desarrollo o CI donde no haya un servidor S3 activo, el servicio soporta un modo de respaldo en sistema de archivos local (`storage/football-s3/`) con generación de URLs firmadas HMAC para que las pruebas corran de forma 100% autónoma y reproducible.

### D-03: Convivencia y extensión de la tabla `dataset_samples`
- **Contexto:** La tabla `dataset_samples` ya fue creada en la migración `b28e1c5f3a71` (HU-17) con campos generales de captura (`discipline`, `challenge`, `hardware_info`, `signed_consent`, `file_format`, `file_size_bytes`, `file_hash_sha256`, `storage_path`, `uploaded_by_id`). El instructivo de fútbol (sección 6) requiere además `participant_id` (`participante_id`), `level_label` (`nivel_etiquetado`), `manual_touch_count` (`conteo_manual`), `noise_level` (`ruido`), `surface` (`superficie`) y `split` (`particion`).
- **Decisión:** Conservar intactas las columnas y restricciones existentes de `dataset_samples` para no romper la HU-17 y añadir mediante una nueva migración de Alembic las columnas opcionales específicas de etiquetado y partición de fútbol (`participant_id`, `level_label`, `manual_touch_count`, `noise_level`, `surface`, `split`).

### D-04: Cola de tareas Celery + Redis con modo síncrono (`task_always_eager`) en pruebas
- **Contexto:** La Fase 0 requiere Celery + Redis y verificar que una tarea Celery de prueba (`process_session`) se ejecute correctamente en CI sin depender obligatoriamente de un broker Redis externo durante `pytest`.
- **Decisión:** Configurar la aplicación Celery en `backend/app/football/tasks.py` conectada a `REDIS_URL` (`redis://localhost:6379/0` por defecto) y permitir `CELERY_TASK_ALWAYS_EAGER` en pruebas unitarias/integración para verificar la ejecución de extremo a extremo de `process_session(session_id)`.

### D-05: Autenticación en WebSocket (`/sessions/{id}/ws`)
- **Contexto:** Los navegadores web no permiten enviar encabezados `Authorization: Bearer <token>` arbitrarios fácilmente en el constructor estándar de `WebSocket`.
- **Decisión:** Soportar el token JWT tanto por query param (`?token=<jwt>`) como por encabezado `Authorization: Bearer <jwt>` en el handshake del WebSocket, verificando siempre que `session.user_id == current_user.id`.

---

## Fase 1 — Captura y Subida por Fragmentos

### D-06: Registro de fragmentos e idempotencia en `evidence_files`
- **Contexto:** `PUT /sessions/{id}/chunks/{n}` exige idempotencia (repetir el mismo fragmento tras un corte de red no debe duplicar registros ni archivos) y `GET /sessions/{id}` debe informar al cliente qué fragmentos ya están confirmados para reanudar desde el último.
- **Decisión:** Registrar cada fragmento confirmado en `evidence_files` con `tipo = "chunk:{n}"` y su `sha256`. Si el cliente reenvía el mismo `chunk_index` con idéntico `sha256`, el backend devuelve `200 OK` con `idempotent_replay: true` sin volver a subir a Garage S3. Además, `GET /sessions/{id}` expone `confirmed_chunks: list[int]`.

### D-07: Ensamblado de fragmentos en Garage S3 al finalizar (`POST /sessions/{id}/finalize`)
- **Contexto:** Al finalizar una grabación de ~40 s (8 fragmentos de 5 s), el servidor debe verificar que todos los fragmentos `0..N-1` estén completos, ensamblarlos en el almacenamiento S3 con su hash SHA-256, cambiar el estado a `processing`, encolar `process_session(session_id)` y responder `202 Accepted`.
- **Decisión:** `GarageS3StorageService.assemble_session_chunks` verifica la secuencia contigua `0..N-1`, concatena los fragmentos en orden, sube el archivo ensamblado a `s3://skillmatch-football/sessions/{session_id}/assembled/recording.mp4`, registra la fila `tipo = "video"` en `evidence_files` con el `sha256` global y dispara `process_session.delay(str(session_id))`.

---

## Fase 2 — Seguimiento del Balón y Detección de Toques por Video

### D-08: Detector clásico híbrido MOG2 + Contornos Circulares + Hough con interfaz intercambiable (`BallDetectorProtocol`)
- **Contexto:** Cuando el balón alcanza el ápice superior de su parábola vertical, su velocidad instantánea se aproxima a cero durante 1–2 fotogramas, lo que puede atenuar temporalmente la máscara pura de movimiento MOG2.
- **Decisión:** Combinar la máscara de sustracción de fondo MOG2 morfológicamente filtrada con umbralización de luminancia/circularidad y `cv2.HoughCircles` como respaldo, integrando un filtro de Kalman lineal 4D (`[x, y, vx, vy]`) e interpolación lineal para huecos de hasta 5 fotogramas, detrás del protocolo `BallDetectorProtocol` para permitir enchufar luego una red tipo TrackNet en ONNX sin tocar el pipeline.

---

## Fase 3 — Audio y Fusión Audio-Video

### D-09: Espectrograma Mel en 200–4000 Hz y Flujo Espectral con `mediana + k·MAD` (`audio_events`)
- **Contexto:** La sección 8 especifica audio mono a 48 kHz, espectrograma Mel en la banda ~200–4000 Hz, flujo espectral y selección de picos con umbral adaptativo (`mediana + k·MAD`) mientras no esté activo el clasificador CNN propio.
- **Decisión:** Implementar el banco de filtros Mel triangular (32 bandas en 200–4000 Hz) con STFT de paso de 5 ms (240 muestras a 48 kHz) sobre `scipy.signal.stft` y `scipy.io.wavfile` (evitando bloqueos de compilación numba en Python 3.14+), dejando el protocolo `AudioImpactClassifierProtocol` listo para enchufar la CNN en ONNX en la Fase 7.

### D-10: Fusión con compensación de calibración, emparejamiento ±70 ms, coherencia y deriva (`fusion`)
- **Contexto:** La fusión debe estimar el desfase con el toque de calibración, emparejar eventos de video y audio con tolerancia de ±70 ms (`confirmed`, `video_only`, `audio_only`), calcular la coherencia (`confirmados / total`) y la deriva (pendiente de regresión lineal en `ms/min`), además de mejorar la precisión del conteo frente a solo video cuando hay oclusiones visuales breves.
- **Decisión:** `fuse_audio_video_events` compensa primero el offset de calibración, realiza emparejamiento bipartito voraz por menor residuo dentro de ±70 ms, calcula la deriva con `np.polyfit` escalada a `ms/min` y, cuando la coherencia de la sesión es legítima (`>= 0.50`), rescata eventos de una sola modalidad con confianza alta para recuperar toques ocultos en video.

---

## Fase 4 — Retos Dinámicos («El Entrenador Dice»)

### D-11: Evaluación de cumplimiento por tramo (`0..1` con tolerancia lineal) y detección de incoherencia de plan (`challenge_engine`)
- **Contexto:** Cada tramo (`LOW`, `HIGH`, `SLOW`, `FAST`) requiere evaluar la mediana de alturas de pico (en diámetros de balón) o la mediana de intervalos entre toques (en segundos) con un puntaje continuo de `0` a `1` con tolerancia, medir la latencia de reacción desde la orden hasta el primer cambio de comportamiento y detectar si el video fue pregrabado con otro plan.
- **Decisión:** `evaluate_challenge_plan` extrae la altura máxima alcanzada por el balón en el arco posterior a cada toque y el intervalo entre toques consecutivos dentro del tramo, aplica una rampa de tolerancia lineal alrededor de los umbrales de `config.yaml` (`1.5` y `3.0` diámetros; `1.0` y `0.6` s), mide la latencia hasta el primer toque que cumple la consigna del tramo y marca `plan_coherent = False` si el cumplimiento medio cae por debajo de `0.55` o más de un tercio de los tramos son incoherentes (`< 0.35`).

---

## Fases 5, 6, 7 y 8 — Características, Scoring, Antifraude, Entrenamiento ONNX e Informe Final

### D-12: Clasificador de nivel por reglas calibradas e intercambio en caliente por modelo ONNX (`scoring` y `model_versions`)
- **Contexto:** La Fase 5 requiere un clasificador inicial basado en reglas sobre los umbrales de `config.yaml` con probabilidades calibradas y retroalimentación determinística por plantillas, mientras que la Fase 7 exige entrenar un modelo sobre participantes agrupados sin fuga (`participant_id`), exportarlo a ONNX y activarlo desde `model_versions` sin cambiar el código.
- **Decisión:** Implementar `RuleBasedLevelClassifier` como línea base y `TrainedArtifactLevelClassifier` como cargador de artefactos `.onnx` registrados en la tabla `model_versions` (`activa = True`). Cuando existe una fila activa en `model_versions`, `evaluate_and_persist_session_result` la utiliza automáticamente y registra su `version_modelo` (`level_classifier:1.0.0-onnx`).

### D-13: Motor de señales antifraude ponderadas (`fraud`)
- **Contexto:** La Fase 6 requiere combinar las 10 señales antifraude (baja coherencia A/V, deriva de reloj, pérdida de foco/pestaña, cortes/fotogramas repetidos, cámara inestable, balón/persona fuera de cuadro, múltiples rostros, latencia de reacción irreal `< 150 ms` o ausente, secuencia de plan incoherente e inconsistencia de duración) en un puntaje de `0` a `100` sin descartar sesiones en silencio.
- **Decisión:** `evaluate_fraud_signals` evalúa cada señal contra los pesos configurables de `config.yaml`, persiste cada incidencia en `fraud_incidents` y marca `requiere_revision = True` (`estado = "needs_review"`) cuando el puntaje supera `review_risk_threshold` (`50.0`) o la confianza del clasificador es menor a `0.55`.





