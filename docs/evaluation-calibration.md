# Comprobación compartida del ambiente — SM-44 (motor de integridad, T9)

Después del consentimiento, el miembro completa una calibración guiada: **movimiento de cabeza, cinco puntos de mirada (centro y cuatro esquinas), silencio y lectura de la frase de control**. **No inicia ni consume el intento.** Esta calibración usa **el mismo motor de integridad que la supervisión** (`backend/app/services/integrity/`): los mismos analizadores (MediaPipe 3D, YuNet/SFace, VAD, diarización, huella de voz, correlación voz-labios) y el mismo módulo de umbrales (`thresholds.py`, constantes `CAL_*` para lo propio de la calibración). `CalibrationProfile` (`integrity/calibration.py`) devuelve comprobaciones con nombre y un motivo en español cada una.

**Estado: prototipo, no certificado anticopia.** Los umbrales están ajustados con señales sintéticas (T11 los ajusta con grabaciones reales). Faltan pruebas físicas de cámara/micrófono, evaluación de falsos positivos/negativos y revisión independiente. Nada de esto es un modelo PAD ni lectura labial.

## Qué produce

Una calibración aprobada guarda, solo en el servidor (columnas JSON nulables de `evaluation_calibration_challenges`, migración `f3a8d2c19e47`):

| Dato | Para qué |
|---|---|
| `gaze_zone` | Zona de pantalla (centro + 4 esquinas + margen) con la que la supervisión juzga la mirada |
| `voiceprint` | Huella de voz y piso de ruido ambiente (`ambient_rms`) para propiedad de la voz y `BACKGROUND_AUDIO` |
| `occlusion_ref` | Referencia de píxeles de rostro/boca descubiertos para `FACE_OCCLUDED` / `MOUTH_OCCLUDED` |

Ninguno se devuelve al cliente: las respuestas solo tienen booleanos (`checks`). Sin los tres datos **no hay `READY_FOR_THEORY`**, aunque todas las comprobaciones sean verdaderas. `EvaluationCalibrationService.valid_seed(db, user)` devuelve zona, huella, piso ambiente y referencia de la última calibración **válida** del miembro (todas las comprobaciones, mismo enrolamiento, menos de 12 h, datos legibles) y `BrowserSupervisionService.start` siembra con ella un ensayo nuevo; sin calibración válida el ensayo arranca sin sembrar y usa sus propios endpoints de calibración (página de prueba). La supervisión sigue sin conectarse a los flujos de examen.

## Cómo se realiza

1. Mis habilidades → Validar habilidad → instrucciones → consentimiento.
2. **Preparar cámara y micrófono** (permisos solo al pulsar). Rostro centrado, buena luz, sin otras personas.
3. Mirar el centro y cada esquina de la pantalla (hasta 6 imágenes por punto).
4. Movimiento: centro → lado de la flecha → centro (imágenes separadas ~1 s).
5. Silencio de 2 a 4 s; después 7 a 10 s de voz y pausa con video simultáneo y lecturas de boca del navegador: la frase primero, **silencio desde el segundo 4,5**.
6. El backend evalúa todo; si falla, muestra el mensaje exacto (`message`) y se puede repetir sin gastar el intento.

## Contrato

Requiere MEMBER, evaluación propia, consentimiento y enrolamiento facial.

| Operación | Efecto |
|---|---|
| `POST /api/evaluations/{id}/liveness/challenge` | Reto TURN_LEFT/TURN_RIGHT de 45 s; reemplaza anteriores |
| `POST /api/evaluations/{id}/liveness/verify-identity` | Valida toda la evidencia; consume solo el reto exitoso, nunca el intento |
| `GET /api/evaluations/{id}/environment/verify` | Consulta la aprobación guardada, no reevalúa |

`CalibrationVerifyRequest` (`extra="forbid"`; **todos los campos son obligatorios salvo `camera_label`**: una solicitud con la forma anterior responde 422 «El campo 'gaze_points' es obligatorio…» y nunca queda lista):

| Campo | Tipo y límites |
|---|---|
| `challenge_id` | UUID del reto vigente |
| `frames` | 3–12 JPEG base64 (≤ 200000 caracteres), movimiento de cabeza |
| `gaze_points` | exactamente 5 `{target, frames}`: `target` ∈ CENTER, TOP_LEFT, TOP_RIGHT, BOTTOM_LEFT, BOTTOM_RIGHT (uno por cada uno); `frames` 1–6 JPEG base64 |
| `ambient_audio_samples` | PCM mono 16 kHz, 32000–64000 valores finitos en [-1,1] (silencio, 2–4 s) |
| `audio_samples` | PCM mono 16 kHz, 112000–160000 valores en [-1,1] (frase y pausa, 7–10 s) |
| `spoken_frames` | 20–100 `{time_ms 0–10000, image ≤ 80000}` muestreados durante `audio_samples` (ordenados, sin huecos > 350 ms, ≤ 640 px de ancho) |
| `mouth_samples` | 8–450 `{t_ms 0–10000 entero, mouth_open 0–2}` del navegador; `t_ms` desde el inicio de `audio_samples`, creciente, ≥ 30 ms de separación |
| `camera_label` | ≤ 200 caracteres; **lo envía el cliente, es solo orientativo** (la señal del servidor es la comprobación de imagen congelada/en bucle) |

Respuesta (`CalibrationStateResponse`): `evaluation_id`, `ready`, `status` (`READY_FOR_THEORY`/`PENDING_CALIBRATION`), `started_at` (`null`), `checks` (nombre → booleano). Un éxito trae las 21 comprobaciones: `lighting`, `sharpness`, `framing`, `passive_screen_check`, `camera_live`, `single_face`, `face_uncovered`, `mouth_uncovered`, `identity`, `frontal`, `liveness`, `occlusion_reference`, `gaze_zone`, `background_quiet`, `microphone`, `speech_pause`, `single_speaker`, `no_overlap`, `mouth_telemetry`, `mouth_audio_sync`, `voiceprint`. Las aprobaciones anteriores (12 comprobaciones, sin zona ni huella) ya no proyectan preparación, y cambiar el enrolamiento también la invalida. Reto usado 409, vencido 410; repetir no consume intentos.

## Qué se comprueba (todo con el motor compartido)

| Paso | Comprobaciones |
|---|---|
| Movimiento | Una sola persona en cada imagen (confirmación frame a frame); cámara no tapada ni congelada ni en bucle (≥ 3 imágenes distintas); rostro y boca descubiertos (carrera continua ≥ 1 s) y referencia de oclusión construida; iluminación (gris medio 0,15–0,98), enfoque, encuadre y confianza del rostro; patrón de pantalla (heurística FFT); identidad SFace en cada imagen; pose frontal al empezar y al terminar (yaw 3D y mirada) y **giro pedido medido con la pose 3D de MediaPipe**, no con razones 2D |
| Zona de mirada | Los cinco puntos distinguibles entre sí, sin segunda persona y con el rostro del centro igual al enrolado (`gaze.compute_zone`) |
| Silencio | VAD WebRTC modo 3 sin voz (< 5 ventanas vocales y < 3 seguidas) y RMS ≤ 0,012 |
| Voz | ≥ 10 ventanas vocales, 3 seguidas y RMS ≥ 0,003; ≥ 3 s de voz; **una sola voz** (diarización sherpa-onnx, sin superposición ≥ 0,12 s; segmentos fuera del audio se descartan); sin voz desde el segundo 4,5; identidad al inicio, mitad y final |
| Boca y voz | Las lecturas de boca del navegador se cotejan con las que el servidor mide en `spoken_frames` (mecanismo de `CLIENT_MISMATCH`): **telemetría no verificable rechaza**; la voz debe seguir a la boca (correlación temporal) |
| Huella | Segmentos de voz coherentes entre sí → huella ERes2Net 512-d con el piso de ruido |

Sin YuNet, SFace y el landmarker 3D, o sin el detector de voz o los modelos de hablantes: **503** («Los modelos locales de calibración no están disponibles.», «…de hablantes no están disponibles.»), nunca aprobación degradada. **Sin el modelo de embeddings de hablante no se puede inscribir la huella y la calibración no queda lista** (estado actual de esta máquina: `speaker_embedding.onnx` no instalado, ver `odd/tasks/anti-cheat-integrity-engine.md` L14).

## Endpoint de la prueba (`/app/browser-supervision-test`)

`POST /api/browser-supervision/trials/{id}/voice-calibration` también exige imágenes: a las lecturas de boca (`mouth_samples`, `t_ms` desde el inicio del audio) se suma `frames`, **20–130 `{t_ms 0–12000 entero, image ≤ 80000}`** muestreados durante la grabación (crecientes, ≥ 40 ms de separación, dentro del audio). El servidor mide la boca en ellas y rechaza (400) telemetría no verificable (`UNTRUSTED_TELEMETRY`), más de un rostro, ningún rostro o imágenes ilegibles; sin modelos de visión, 503. La respuesta sigue siendo `{voice_enrolled, voiced_seconds}`. Un ensayo nuevo se siembra con la calibración válida del miembro si la hay.

## Qué se estima localmente y límites

- **Voz y hablantes:** `webrtcvad-wheels==2.0.14`, `sherpa-onnx==2.0.1`, Pyannote 3.0 y 3D-Speaker locales, CPU/un hilo. Umbral de agrupamiento 0,5: experimental. Instalación/hashes: [`models/audio-integrity/README.md`](models/audio-integrity/README.md). **No se descargan modelos durante solicitudes.**
- **Boca/voz:** apertura de boca (`jawOpen` + razón de aspecto de labios, la misma fórmula en navegador y servidor) correlacionada con la energía de la voz (r ≥ 0,45, desfase −90…+300 ms, solapamiento ≥ 0,30). La heurística de parches de boca de YuNet **ya no existe**.
- Los resultados son **indicios**: no identifican WhatsApp, quién habla ni las palabras; imitar movimiento, replays/deepfakes, cámara virtual con etiqueta falsa, mezcla débil o ruido pueden evadirlos y una persona legítima puede ser rechazada por compresión, luz, encuadre o sincronía del navegador. El modelo de embeddings se distribuye como `zh-cn`; no hay validación con hablantes de español ni de equidad/accesibilidad. No promover a producción sin evaluar esto (T11).
- **Privacidad:** imágenes y audios no se guardan; se guardan metadatos, booleanos, la zona, la huella de voz (biométrico) y la referencia de oclusión, y nunca salen del servidor.
- Una calibración aprobada no significa examen iniciado. `TheoryExamService.start` sigue exigiendo `READY_FOR_THEORY` completo.

Evidencia de pruebas en `odd/tasks/anti-cheat-integrity-engine.md`; las pruebas con grabaciones reales quedan para T11.
