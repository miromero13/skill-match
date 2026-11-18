# Comprobación compartida del ambiente — SM-44

Después de aceptar el consentimiento de SM-23, el miembro puede preparar cámara y micrófono, realizar un reto breve y consultar el resultado. Esta etapa es común a todas las habilidades y **no inicia ni consume el intento**.

**Estado:** implementación de prototipo con pruebas automatizadas. Prueba real de cámara diferida por el usuario («luego pruebo»). La eficacia biométrica, del reto motor y de las heurísticas de pantalla no está acreditada por esas pruebas; no considerar esta entrega una certificación de seguridad ni una defensa validada contra deepfakes.

## Recorrido en la interfaz

1. Mis habilidades → Validar habilidad → instrucciones → consentimiento.
2. Pulsar **Preparar cámara y micrófono**. No se solicitan permisos automáticamente.
3. Ajustar iluminación y encuadre; debe verse una sola persona. Esperar a que aparezca la imagen.
4. Pulsar **Comprobar ambiente e identidad**.
5. Mirar al centro, girar hacia el lado indicado de la vista previa y regresar al centro. Decir «listo» durante la captura para comprobar señal del micrófono.
6. Corregir el ambiente y repetir si hay un rechazo. No se consume el intento.
7. Si la comprobación es satisfactoria, se muestra el desglose y se apagan los periféricos. El examen sigue sin comenzar; SM-39 debe implementar su inicio real y SM-49 la supervisión continua.

También se liberan cámara y micrófono al salir o pulsar **Cerrar cámara y micrófono**. La calibración no implementa aún monitoreo continuo después de esta captura.

## API

Requiere sesión MEMBER, evaluación propia pendiente de calibración, consentimiento persistido y enrolamiento facial.

| Operación | Efecto |
|---|---|
| `POST /api/evaluations/{id}/liveness/challenge` | Reto aleatorio TURN_LEFT/TURN_RIGHT válido cinco segundos; reemplaza retos anteriores y deja la evaluación pendiente de comprobación |
| `POST /api/evaluations/{id}/liveness/verify-identity` | Valida la secuencia, el audio y la identidad; un éxito consume el reto, no el intento de examen |
| `GET /api/evaluations/{id}/environment/verify` | Consulta el resultado guardado; invalida su preparación si cambió el enrolamiento. No captura ni comprueba de nuevo el ambiente actual |

El POST de verificación recibe `challenge_id`, `frames` (3–12 JPEG base64 acotados), `audio_samples` (16–4096 valores entre -1 y 1) y `camera_label`. La interfaz captura nueve imágenes durante aproximadamente 2,8 segundos, a un máximo de 640 píxeles de ancho, y envía una muestra de audio con señal. El reto puede expirar por lentitud de captura o transporte: se pide uno nuevo, sin descontar el intento.

Una respuesta satisfactoria indica `ready: true`, estado `READY_FOR_THEORY`, `started_at: null` y el desglose de comprobaciones. Un reto usado devuelve 409 y uno vencido 410. Los errores usan el sobre APIResponse y la interfaz muestra su `message`.

## Qué se comprueba y cuáles son sus límites

| Control | Implementación | Límite |
|---|---|---|
| Imagen | JPEG con dimensiones acotadas antes de decodificar | No acepta cualquier formato de imagen ni valida una cámara física |
| Iluminación y encuadre | Brillo, enfoque, tamaño y posición del rostro | Umbrales de prototipo pendientes de probar con cámaras reales |
| Presencia | YuNet local: exactamente un rostro por frame | Solo observa lo visible en cámara, no inspecciona toda la habitación |
| Identidad | SFace local contra el vector enrolado; umbral propio de SFace | No usar un porcentaje arbitrario de otro modelo; eficacia real pendiente |
| Prueba de vida | Cambio relativo de posición de nariz/ojos en el sentido aleatorio y regreso al centro | Heurística motora; no demuestra resistencia a videos preparados o deepfakes |
| Patrones de pantalla | Indicador experimental de periodicidad de textura | No es un modelo PAD entrenado ni prueba que no haya una pantalla |
| Micrófono | Energía de una muestra capturada por Web Audio | No identifica otras voces ni certifica el hardware; SM-49 es otra tarea |
| Cámara virtual | Etiquetas conocidas, con enumeración de dispositivos en frontend | Heurística evadible; una etiqueta no garantiza cámara física |

Las comprobaciones de calibración usan instancias propias de los modelos y **no recurren al respaldo sintético del servicio de perfil**. Imágenes inválidas se rechazan. Si faltan modelos locales se responde 503; no se autoriza por degradación.

Los frames, el audio y los embeddings calculados no se guardan en la tabla de retos ni se escriben como archivos por esta implementación. Se conservan metadatos del reto, referencia de enrolamiento y resultados booleanos. Los procesamientos permanecen en infraestructura propia.

## Persistencia e integración siguiente

La migración `a732bd904c11` agrega `evaluation_calibration_challenges` después del merge `99731898af88` que ya estaba en el árbol de trabajo del usuario. No modifica ni reemplaza las migraciones de identidad ni carga datos.

No se aplican migraciones automáticamente a la base local. Debe revisarse la cadena antes de probar en la aplicación.

El futuro inicio de SM-39 debe comprobar la evaluación y su calibración vigente, el enrolamiento correspondiente y los cupos de forma atómica. Solo ese inicio registra `started_at` y consume el intento sin devolución. Consultar un resultado guardado no garantiza que el ambiente actual continúe igual. La vigencia necesaria entre calibración e inicio debe definirse al integrar ese inicio; no convertir el estado guardado en un atajo permanente.

## Verificación

- API en esquema PostgreSQL aislado: `cd backend && .venv/bin/python -m pytest tests/test_evaluation_calibration.py tests/test_evaluation_preflight.py -q`.
- Frontend focalizado: `cd frontend && npm test -- --run src/test/calibration-panel.test.tsx src/test/evaluation-preflight.test.tsx src/test/teaching-skill-session.test.ts`.
- Cadena completa de migraciones verificada en una base PostgreSQL descartable; no aplicada a la base de la aplicación.
- Frontend completo: 33 archivos / 168 pruebas y build TypeScript/Vite correctos. Permanece la advertencia no fatal de bundle mayor de 500 kB.
- Regresión focalizada de calibración/pre-embarque/autenticación administrativa: 24 pruebas correctas, incluida invalidación al cambiar el enrolamiento (`tests/test_calibration_enrollment_change.py`).
- Actualización posterior: correcciones de fixtures y expectativas autorizadas por separado; suite backend completa en copia/base descartables: **648 correctas, 0 fallas, 1 omitida por credenciales Garage S3 no configuradas** (exit 0). Migraciones exit 0 y base temporal eliminada. Ver `docs/backend-test-isolation.md`. Esto resuelve el bloqueo de la suite, no la revisión independiente ni la prueba real de cámara.
- Evidencia histórica previa: suite backend general en copia y base descartables: 631 correctas, 16 fallidas, 1 omitida (exit 1). El primer intento falló al recolectar por imports relativos de pruebas; se corrigió PYTHONPATH en el runner aislado, no en la aplicación. Las 16 fallas afectan administración, migraciones, sesión, catálogo, WebSocket y moderación; su atribución requiere diagnóstico separado. El runner usa configuración ficticia, por lo que no equivale a demostrar 16 defectos de aplicación ni a declarar fallas preexistentes. La razón de la omisión no fue expuesta por la ejecución `-q`.
- Los éxitos de visión de las pruebas de ciclo de vida usan dobles. Las pruebas UI simulan dispositivos y captura. No acreditan funcionamiento con una persona real ni eficacia anti-spoofing.
- La revisión independiente de seguridad/concurrencia permanece pendiente; no se ejecutaron subagentes, de acuerdo con la instrucción del usuario.
