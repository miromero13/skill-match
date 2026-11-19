# Corrección de respuestas teóricas

La corrección externa de texto permanece deshabilitada por defecto. Se puede elegir Gemini u OpenAI en la configuración del backend; el modelo debe declararse explícitamente y la clave aplicable nunca sale del servidor. La transmisión requiere consentimiento informado del miembro. No se transmite audio, video, identidad ni metadatos de cuenta.

El adaptador usa endpoints HTTPS fijos, tiempo límite acotado y salida JSON estructurada. La salida se valida contra criterios de rúbrica; el servidor calcula puntos ponderados. El proveedor/modelo/prompt y versiones de preguntas quedan fijados al inicio; las respuestas y el estado de resultado son persistentes. Errores quedan pendientes de reintento sin nota sintética y no alteran recibos ni intentos. Esto no acredita eficacia de proveedores reales.

Configurar las variables `THEORY_GRADING_PROVIDER`, `THEORY_GRADING_MODEL`, `OPENAI_API_KEY` o `GEMINI_API_KEY`, y `THEORY_GRADING_TIMEOUT_SECONDS` como se documenta en [backend/README.md](../backend/README.md). No configurar una clave o proveedor no habilita una alternativa automática.
