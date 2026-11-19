"""The Spanish reasons shown verbatim to the member when a calibration step fails (the frontend displays ``message``).

Shared by the trial's calibration endpoints and the pre-exam calibration, so one rule never has two wordings.
Each map is code -> (HTTP status, message).
"""

# Gaze zone (center + four corners).
GAZE_CALIBRATION_ERRORS = {
    "FACE_MISSING": (400, "No pudimos ver tu rostro en todos los puntos. Ubicate frente a la cámara con buena luz "
                          "y repetí la calibración."),
    "MULTIPLE_FACES": (400, "Se detectó más de una persona durante la calibración. Tiene que estar solo tu rostro "
                            "en cámara."),
    "NOT_DISTINGUISHABLE": (400, "No pudimos distinguir hacia dónde mirabas. Mirá cada punto moviendo los ojos o la "
                                 "cabeza hacia esa esquina y repetí la calibración."),
    "MODEL_UNAVAILABLE": (503, "El análisis de mirada no está disponible en este momento. Reintentá más tarde."),
}

# Voice enrollment (silence + control phrase).
VOICE_CALIBRATION_ERRORS = {
    "INSUFFICIENT_SPEECH": (400, "No escuchamos suficiente voz. Leé la frase completa en voz alta y repetí la "
                                 "calibración."),
    "MULTIPLE_SPEAKERS": (400, "Se detectó más de una voz durante la calibración. Tiene que hablar solo vos, sin otras "
                                "personas ni audio reproducido, y repetí la calibración."),
    "INCONSISTENT": (400, "No pudimos confirmar una sola voz constante. Repetí la frase en un ambiente silencioso."),
    "UNSYNCED": (400, "Tu voz no coincide con el movimiento de tus labios. Mirá la cámara, leé la frase en voz alta y "
                      "repetí la calibración."),
    "NO_MOUTH": (400, "No pudimos ver el movimiento de tu boca. Ubicate frente a la cámara con la boca descubierta y "
                      "repetí la calibración."),
    "AMBIENT_NOT_QUIET": (400, "Había voces o ruido durante el silencio inicial. Buscá un ambiente en silencio y "
                               "repetí la calibración."),
    "UNTRUSTED_TELEMETRY": (400, "No pudimos confirmar el movimiento de tu boca con las imágenes de la cámara. Mantené "
                                 "la página visible, mirá a la cámara y repetí la calibración."),
    "MULTIPLE_FACES": (400, "Se detectó más de una persona mientras grababas la voz. Tiene que estar solo tu rostro en "
                            "cámara."),
    "NO_FACE": (400, "No pudimos ver tu rostro mientras grababas la voz. Ubicate frente a la cámara con buena luz y "
                     "repetí la calibración."),
    "NO_VIDEO": (400, "No se obtuvo video sincronizado suficiente. Mantené la página visible y repetí la calibración."),
}
VOICE_UNAVAILABLE = (503, "La verificación de voz no está disponible en este momento. Reintentá más tarde.")
VOICE_VISION_UNAVAILABLE = (503, "El análisis de video de la voz no está disponible en este momento. Reintentá más tarde.")
VOICE_CALIBRATION_ERRORS["VISION_UNAVAILABLE"] = VOICE_VISION_UNAVAILABLE

# Pre-exam calibration steps (the wording the member saw before the unification is kept where the rule is kept).
INVALID_IMAGE = "La captura de calibración no es una imagen JPEG válida."
IMAGE_SIZE = "La cámara debe entregar imágenes JPEG entre 320×240 y 1280×960."
DIFFERENT_FRAMES = "La prueba de vida requiere una secuencia de imágenes diferentes."
PHYSICAL_CAMERA = "Seleccioná una cámara física para la calibración."
CAMERA_BLOCKED = "La cámara parece tapada o apagada. Descubrila y repetí la comprobación."
CAMERA_FROZEN = "La imagen de la cámara no cambia. Usá una cámara física en vivo y repetí la comprobación."
LIGHTING = "Iluminación insuficiente o excesiva. Ajustá la luz del ambiente y repetí la comprobación."
SINGLE_FACE = "Debe verse una sola persona durante toda la calibración."
FRAMING = "Ubicá tu rostro dentro del encuadre y acercate a la cámara."
SHARPNESS = "La imagen está desenfocada. Ajustá la cámara y repetí la comprobación."
SCREEN_PATTERN = "Se detectaron patrones de imagen sospechosos. Evitá pantallas frente a la cámara y repetí la comprobación."
IDENTITY = "El rostro de la cámara no coincide con tu enrolamiento."
IDENTITY_UNKNOWN = "No se pudo extraer un rostro válido para la calibración."
FACE_COVERED = "Tenés el rostro tapado. Descubrilo por completo y repetí la comprobación."
MOUTH_COVERED = "Tenés la boca tapada. Descubrila y repetí la comprobación."
OCCLUSION_UNJUDGED = ("No se pudo comprobar que el rostro y la boca estén descubiertos. Mirá al frente con buena luz y "
                      "repetí la comprobación.")
FRONTAL = "Mirá de frente a la pantalla al empezar y al terminar el movimiento y repetí la comprobación."
LIVENESS = "No se completó el movimiento solicitado. Mirá al centro, girá hacia el lado indicado y volvé al centro."
POSE_3D_UNAVAILABLE = "El análisis de pose 3D no está disponible en este momento. Reintentá más tarde."
VISION_UNAVAILABLE = "Los modelos locales de calibración no están disponibles."
AUDIO_SIZE = "El audio debe incluir fondo de 2 a 4 segundos y voz de 7 a 10 segundos a 16000 Hz."
VAD_UNAVAILABLE = "El detector local de voz no está disponible."
SPEECH_DURING_SILENCE = ("Se detectó voz durante el silencio. Pausá llamadas, videos o conversaciones y repetí la "
                         "comprobación.")
BACKGROUND_NOISE = "Hay demasiado ruido de fondo. Buscá un ambiente más silencioso y repetí la comprobación."
NOT_ENOUGH_SPEECH = ("No se detectó voz suficiente. Decí «Estoy listo para comenzar» cuando se indique y repetí la "
                     "comprobación.")
SPEECH_DURING_PAUSE = ("Se detectó voz durante la pausa. Guardá silencio cuando termine la frase y pausá llamadas o "
                       "conversaciones.")
SPEAKER_MODELS_UNAVAILABLE = "Los modelos locales de hablantes no están disponibles."
MORE_THAN_ONE_VOICE = "Se detectaron indicios de más de una voz. Pausá llamadas y conversaciones y repetí la comprobación."
OVERLAPPING_VOICES = ("Se detectaron indicios de voces superpuestas. Buscá un ambiente sin conversaciones y repetí la "
                      "comprobación.")
SINGLE_VOICE_UNCONFIRMED = "No se pudo confirmar una sola voz con suficiente evidencia. Repetí la frase con voz clara."
VOICE_VIDEO = "No se obtuvo video sincronizado suficiente. Mantené la página visible y repetí la comprobación."
VOICE_SINGLE_FACE = "Debe verse una sola persona durante toda la comprobación de voz."
VOICE_WITHOUT_MOUTH = ("Se detectó voz sin movimiento de boca coincidente. Repetí mirando a cámara y hablando solo cuando se "
                      "indique.")
VOICE_IDENTITY = "El rostro durante la prueba de voz no coincide con tu enrolamiento."
INCOMPLETE = "La calibración no completó todas las comprobaciones."
