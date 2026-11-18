# Comprobación compartida del ambiente — SM-44

Después del consentimiento, el miembro completa una secuencia automática de movimiento, fondo silencioso y voz con video simultáneo. **No inicia ni consume el intento.** El backend evalúa el conjunto; no hay una aprobación anticipada del movimiento.

**Estado: prototipo, no certificado anticopia.** Las pruebas de políticas y dos ensayos nativos de audio pasan. Faltan pruebas físicas de cámara/micrófono, evaluación de falsos positivos/negativos y revisión independiente. El movimiento de boca es una heurística visual, no un modelo entrenado de lectura labial ni una prueba PAD.

## Cómo se realiza

1. Mis habilidades → Validar habilidad → instrucciones → consentimiento.
2. Pulsar **Preparar cámara y micrófono** y conceder permisos. No se activan automáticamente.
3. Centrar el rostro, iluminarlo y pausar llamadas, videos y conversaciones.
4. Pulsar **Comprobar ambiente e identidad** una vez:
   - **Movimiento, 11 segundos:** centro → lado de la flecha → centro; sin hablar.
   - **Fondo, 3 segundos:** guardar silencio.
   - **Voz y pausa, 8 segundos, con video simultáneo:** durante los primeros4 segundos aparece **Decí: «Estoy listo para comenzar».** Después aparece **Ahora guardá silencio y mantené la boca quieta.** por otros4 segundos.
5. Esperar el resultado del backend. No hay botones entre etapas. La captura dura unos22 segundos, más transporte y procesamiento.
6. Si se rechaza, se muestra el mensaje exacto del backend y se puede repetir sin gastar el intento.

La vista previa se refleja por CSS, nunca los JPEG enviados. `TURN_LEFT` de la imagen original corresponde a la derecha del miembro; `TURN_RIGHT`, a su izquierda. Las doce imágenes iniciales se toman durante11 segundos; la guía cambia después de las imágenes cuarta y octava.

Las imágenes de voz se capturan aproximadamente cada100ms según las muestras PCM recibidas, no según un temporizador independiente. El grabador comprueba continuidad del reloj Web Audio; si faltan bloques o evidencia suficiente, rechaza. Se usa salida muda y se solicitan desactivadas cancelación de eco, supresión de ruido y ganancia automática, sujetos al soporte del navegador. Salir, volver a Normas, cerrar o completar libera dispositivos y cancela buffers/eventos pendientes.

## Contrato y compatibilidad

Requiere MEMBER, evaluación propia, consentimiento y enrolamiento facial.

| Operación | Efecto |
|---|---|
| `POST /api/evaluations/{id}/liveness/challenge` | Reto TURN_LEFT/TURN_RIGHT de45 segundos; reemplaza retos anteriores |
| `POST /api/evaluations/{id}/liveness/verify-identity` | Valida evidencia; consume solo el reto exitoso, nunca el intento |
| `GET /api/evaluations/{id}/environment/verify` | Consulta la aprobación guardada, no reevalúa el ambiente actual |

Campos de verificación:

| Campo | Límite |
|---|---|
| `challenge_id` | Reto vigente |
| `frames` | 3–12 JPEG base64, hasta200000 caracteres cada uno, movimiento inicial |
| `camera_label` | Hasta200 caracteres |
| `ambient_audio_samples` | PCM mono16kHz,32000–64000 valores finitos en[-1,1], fondo2–4s |
| `audio_samples` | PCM mono16kHz,112000–160000 valores finitos en[-1,1], voz/pausa7–10s; normalmente8s |
| `spoken_frames` | 20–100 objetos `{time_ms, image}`; JPEG hasta80000 caracteres, tiempos finitos0–10000ms |

Los tiempos deben estar ordenados, cubrir la ventana de audio y no tener huecos mayores de350ms; separación mediana máxima200ms. El video de movimiento no sustituye al video de voz. El servidor valida además JPEG y resolución antes de inferir.

Un éxito devuelve `ready:true`, `READY_FOR_THEORY`, `started_at:null` y doce comprobaciones: `lighting`, `framing`, `single_face`, `microphone`, `background_quiet`, `identity`, `liveness`, `passive_screen_check`, `single_speaker`, `no_overlap`, `mouth_audio_sync`, `speech_pause`. Aprobaciones antiguas sin las nuevas comprobaciones ya no proyectan preparación. Cambiar el enrolamiento también invalida el resultado. El frontend no muestra éxito si un backend antiguo responde preparado sin los nuevos controles.

**Actualizar backend y frontend juntos y reiniciar/recargar.** Los clientes anteriores de voz3s ya no cumplen el contrato. No hay aprobación por RMS ni otro respaldo permisivo. Reto usado409, vencido410; repetir no consume intentos. Si captura/transporte excede45s, pedir otro reto.

## Qué se estima localmente

- **Actividad de voz:** WebRTC VAD modo3, `webrtcvad-wheels==2.0.14`, ventanas30ms. En fondo: rechazo con5 ventanas vocales totales o3 consecutivas, o RMS>0.012. En voz: mínimo10 ventanas vocales,3 consecutivas y RMS≥0.003; la comprobación audiovisual exige además≥0.9s de actividad antes de4.3s. Tras4.5s se vuelve a exigir silencio, tolerando el cambio de instrucción.
- **Hablantes/superposición:** `sherpa-onnx==2.0.1`, Pyannote3.0 y embeddings3D-Speaker locales, CPU/un hilo e instancias por solicitud. Número de hablantes automático, no forzado a uno. Rechazo ante varios grupos, intervalos de hablantes diferentes solapados≥120ms o evidencia insuficiente. Umbral de agrupamiento0.5 y duración vocal mínima1.2s: parámetros experimentales, no calibrados para esta población.
- **Boca/audio:** YuNet local localiza ojos, nariz y comisuras. Se estabiliza la imagen con ojos/nariz; se compara cambio en una región fija de boca contra mejillas y contra la pausa final. Debe haber movimiento coincidente con actividad vocal por encima del fondo. SFace coteja identidad al comienzo, mitad y final; se exige un rostro en cada imagen. No es identidad continua frame a frame.
- **Visión previa:** iluminación, enfoque, encuadre, cotejo de enrolamiento, movimiento y heurística experimental de pantalla. No se usa el respaldo sintético del perfil.

Instalación/procedencia/hashes: [`models/audio-integrity/README.md`](models/audio-integrity/README.md). **No se descargan modelos durante solicitudes.** Modelos de hablantes ausentes/corruptos o detector no disponible:503, nunca aprobación degradada.

## Límites y privacidad

Los resultados son **indicios**, no certeza. No se identifica WhatsApp, quién habla, las palabras pronunciadas ni la fuente física del sonido. No se valida que la frase sea correcta. Una sola voz remota puede confundirse con una voz local; imitar movimiento, replays/deepfakes, cámara virtual, mezcla débil, auriculares o ruido pueden evadir o confundir los controles. La heurística de boca puede rechazar una persona legítima por compresión, iluminación, encuadre, movilidad facial o sincronización del navegador. El modelo de embeddings elegido se distribuye como `zh-cn`; no hay validación de eficacia con hablantes de español ni de equidad/accesibilidad. No promover a producción sin evaluar estos límites.

Imágenes, audios y embeddings calculados no se guardan en archivos ni en la tabla de retos. Solo metadatos, referencia de enrolamiento y booleanos. El costo por solicitud está acotado por las ventanas, imágenes y un hilo nativo; esto **no** prueba capacidad bajo concurrencia ni establece un presupuesto de memoria para despliegue.

Esta actualización no agrega/aplica migraciones, seeds ni cambios en registros manuales. La migración existente `a732bd904c11` crea la tabla de retos. SM-39 todavía debe implementar inicio/debito atómico e idempotente; SM-49, supervisión continua. Una calibración aprobada no significa examen iniciado.

## Evidencia disponible y pendiente

- 39 pruebas focalizadas backend pasan en copia/PostgreSQL descartables: errores HTTP exactos, estado/cupos intactos y reintento con el mismo reto; migración0/pytest0 y base temporal eliminada. Extracción audiovisual y agrupamiento se simulan en esas pruebas: no son prueba física.
- 17 pruebas focalizadas frontend y TypeScript/Vite build pasan: orden22s, video en reloj PCM, ventanas separadas, remuestreo48k→16k, salida muda, guía/pausa y cancelación. No sustituyen navegador físico.
- Inferencia nativa real: grabación pública multihablante56.86s rechazada por varias voces; mezcla local de dos fragmentos en una ventana8s produjo intervalos superpuestos y rechazo específico400. Son dos ensayos puntuales, no validación de eficacia. No se usó audio privado del miembro.
- Aprovisionador probado con los artefactos oficiales ya descargados en estado temporal aislado, sin red, y verificación SHA256 repetida correctamente. Las licencias/procedencia están preservadas.
- Suites completas actuales: **backend670 correctas,1 omitida por Garage S3 y1 advertencia Starlette/httpx**, con migración/pytest exit0 y base descartable eliminada. **Frontend177 correctas/1 fallida** en `evidence-navigation.test.tsx:149`, el mismo fallo de catálogo observado antes; no se modificó ese código. No se informa una suite frontend totalmente verde. TypeScript/Vite build correcto, con la advertencia existente de bundle>500kB. Evidencia final en `odd/tasks/audiovisual-calibration.md`.
- Pendiente prueba manual: silencio real; frase normal seguida de pausa; otra persona hablando; llamada reproducida durante pausa; voz externa con boca quieta; movimientos de cabeza sin hablar; salida/cierre durante captura. Registrar falsos positivos/negativos, sin asumir éxito. Revisión independiente no disponible: el usuario no tiene API keys de subagentes. No se ejecutó ni se atribuye aprobación independiente.
