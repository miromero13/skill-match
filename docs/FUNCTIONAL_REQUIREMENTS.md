# SkillMatch — Especificación de Requisitos Funcionales

*Plataforma web y móvil de intercambio de habilidades con validación mediante Inteligencia Artificial*

---

## 1. Introducción

Este documento define la especificación detallada de los requisitos funcionales (RF) de SkillMatch, organizados por módulo. Incluye los seis módulos del alcance original y tres módulos adicionales (Sesiones de Intercambio, Reputación y Confianza, Notificaciones) que completan el ciclo real de uso y aportan los elementos innovadores del proyecto.

### Convenciones
- **ID**: `RF-<módulo>-<número>` (ejemplos: `RF-USR-01`, `RF-HAB-05`, `RF-MAT-04`).
- **Prioridad**: 
  - **A** = Alta (Alcance MVP indispensable).
  - **M** = Media (Versión 1.0 funcional extendida).
  - **B** = Baja (Versión posterior / evolución).
- **Actores**: Usuario (aprendiz/instructor), Administrador, Moderador/Revisor, Sistema (procesos asíncronos y demonios) y Motor de IA / Inferencia.
- Los requisitos marcados con **★** representan **diferenciadores innovadores**.

---

### 1.1 Restricción de IA Propia (Mandatoria)

SkillMatch **no puede usar proveedores de IA cerrados de pago (OpenAI, Anthropic, Gemini API) ni modelos generativos de terceros en la nube**. Toda la inteligencia de evaluación, extracción de características y clasificación debe ser construida, entrenada y ejecutada por el equipo en infraestructura propia con herramientas open source. Ningún dato de usuario ni evidencia biométrica sale hacia APIs externas.

| Componente | Tratamiento en SkillMatch | Justificación Técnica |
|---|---|---|
| **Librerías y algoritmos clásicos** (OpenCV, librosa, PyTorch, scikit-learn, AST de Python) | **Permitidos** | Son frameworks y herramientas de base matemática/señales, no modelos de terceros empaquetados como servicio. |
| **Modelos entrenados por el equipo** con datasets propios | **Núcleo del sistema** | Clasificadores de nivel, detectores de eventos y redes sobre audio y video. |
| **Modelos preentrenados de terceros** (extractores de pose open-source, detectores faciales estándar) | **Solo como apoyo y declarados** | Requieren inventario formal de componentes y aprobación de la cátedra/docente. |
| **LLMs, modelos generativos o APIs de voz de terceros** | **Fuera de alcance** | La retroalimentación pedagógica y preguntas de defensa se generan determinísticamente con reglas y plantillas. |

---

## 2. Resumen de Elementos Innovadores (★)

| # | Innovación | Módulo | Descripción Sintética |
|---|---|---|---|
| ★1 | **Pasaporte de Habilidades** | `RF-HAB`, `RF-REP` | Perfil verificable con nivel, evidencias y sello con código QR / URL consultable por terceros. |
| ★2 | **Triángulos y cadenas de intercambio** | `RF-MAT` | Si A no tiene match directo con B, el sistema detecta ciclos cerrados de 3 o más personas (A enseña a B, B a C, C a A). |
| ★3 | **Evaluación adaptativa (CAT)** | `RF-EVA` | Ajuste dinámico de dificultad de las preguntas según el desempeño en tiempo real para optimizar la prueba. |
| ★4 | **Entrenador de IA con retroalimentación** | `RF-EVA`, `RF-IA` | Generación de feedback formativo (postura, ritmo, afinación, complejidad) mediante reglas y plantillas basadas en métricas medidas, sin LLMs. |
| ★5 | **Defensa de la solución** | `RF-EVA` | Formulación de preguntas sobre el código analizando su AST para verificar comprensión real y descartar plagio. |
| ★6 | **Puntaje de confianza dinámico** | `RF-REP` | Índice ponderado que combina verificaciones aprobadas, incidencias de fraude, valoraciones y asistencia. |
| ★7 | **Banco de tiempo** | `RF-SES` | Créditos por horas de enseñanza impartidas para poder aprender de terceros sin reciprocidad directa obligatoria. |
| ★8 | **Sesiones asistidas** | `RF-SES` | Generación algorítmica de plan de sesión, objetivos y estructura según nivel del aprendiz. |
| ★9 | **Verificación por pares** | `RF-REP` | Usuarios con nivel Experto validado pueden actuar como revisores de segundo orden y sumar reputación. |
| ★10 | **Ruta de aprendizaje y logros** | `RF-REP` | Visualización de hitos, badges de progresión e itinerario formativo. |

---

## 3. Requisitos Funcionales Detallados

### 3.1 Módulo 1 – Gestión de Usuarios y Accesos (`RF-USR`)

| ID | Requisito Funcional | Prioridad |
|---|---|:---:|
| **RF-USR-01** | El sistema permitirá registrar usuarios con nombre, correo, contraseña, fecha de nacimiento y país/ciudad. | A |
| **RF-USR-02** | El sistema permitirá registro e inicio de sesión mediante proveedores externos (Google, Apple). | M |
| **RF-USR-03** | El sistema verificará el correo electrónico mediante un enlace o código de un solo uso antes de activar la cuenta. | A |
| **RF-USR-04** | El sistema permitirá iniciar y cerrar sesión de forma segura mediante tokens JWT con expiración y renovación (*refresh tokens*). | A |
| **RF-USR-05** | El sistema permitirá recuperar y cambiar la contraseña mediante un enlace temporal firmado. | A |
| **RF-USR-06** | El sistema ofrecerá autenticación en dos pasos (2FA) opcional vía TOTP. | M |
| **RF-USR-07** | El usuario podrá ver y editar su perfil: foto, biografía, idiomas, zona horaria y enlaces externos. | A |
| **RF-USR-08** | El usuario configurará su disponibilidad semanal por franjas horarias y su zona horaria. | A |
| **RF-USR-09** | El usuario seleccionará su modalidad de intercambio: presencial, virtual o ambas, y su radio geográfico para encuentros presenciales. | A |
| **RF-USR-10** | El sistema aplicará control de acceso por roles (Usuario, Administrador, Moderador) restringiendo funciones según el rol (RBAC). | A |
| **RF-USR-11** | El usuario controlará la privacidad de su perfil: qué datos son públicos, visibles solo para matches o privados. | M |
| **RF-USR-12** | El usuario podrá ver y revocar sesiones activas en otros dispositivos. | B |
| **RF-USR-13** | El usuario podrá desactivar o eliminar su cuenta y solicitar la exportación de sus datos personales. | M |
| **RF-USR-14** | El sistema registrará la aceptación de términos, política de privacidad y consentimiento explícito para el uso de cámara, micrófono y procesamiento biométrico. | A |
| **RF-USR-15** | El administrador podrá listar, buscar, suspender, reactivar y bloquear usuarios, indicando motivo y registro de auditoría. | A |
| **RF-USR-16** | El sistema bloqueará temporalmente la cuenta tras superar el límite de intentos fallidos de inicio de sesión. | M |
| **RF-USR-17** | El sistema impondrá una edad mínima y requerirá autorización explícita para menores donde la normativa lo exija. | M |

---

### 3.2 Módulo 2 – Gestión de Habilidades (`RF-HAB`)

| ID | Requisito Funcional | Prioridad |
|---|---|:---:|
| **RF-HAB-01** | El administrador gestionará el catálogo de habilidades (crear, editar, desactivar) categorizado por áreas y subcategorías. | A |
| **RF-HAB-02** | El usuario podrá registrar habilidades que puede enseñar, indicando nivel declarado, años de experiencia y descripción. | A |
| **RF-HAB-03** | El usuario podrá registrar habilidades que desea aprender, indicando nivel actual, nivel objetivo y urgencia. | A |
| **RF-HAB-04** | El sistema diferenciará taxativamente el nivel declarado del nivel verificado (Principiante, Intermedio, Avanzado, Experto). | A |
| **RF-HAB-05** | El sistema mostrará el estado de cada habilidad: *Declarada*, *Pendiente de validación*, *En evaluación*, *Verificada* o *Expirada*. | A |
| **RF-HAB-06** | El usuario podrá editar o eliminar sus habilidades; al modificar una habilidad verificada, el nivel verificado vigente se preservará hasta nueva evaluación. | A |
| **RF-HAB-07** | El usuario podrá sugerir nuevas habilidades al catálogo; el administrador las aprobará o rechazará. | M |
| **RF-HAB-08** | El usuario podrá adjuntar evidencias complementarias (enlaces a repositorios, videos, certificaciones previas). | M |
| **RF-HAB-09** | Las verificaciones tendrán una vigencia parametrizable (ej. 12 meses); el sistema emitirá avisos previos a la expiración y habilitará re-evaluación. | M |
| **RF-HAB-10** | El sistema sugerirá habilidades afines basadas en ontología de catálogo (ej. guitarra acústica → teoría musical). | B |
| **RF-HAB-11 ★** | **Pasaporte de Habilidades**: generación de perfil público verificable con habilidades, niveles certificados, fecha de validación y código QR/URL con firma digital consultable por terceros. | M |
| **RF-HAB-12 ★** | El sistema permitirá exportar el Pasaporte de Habilidades en formato PDF con firma criptográfica institucional de SkillMatch. | B |
| **RF-HAB-13** | El sistema permitirá configurar prerrequisitos entre habilidades (ej. no validar nivel avanzado sin aprobar el nivel previo). | B |

---

### 3.3 Módulo 3 – Evaluación y Validación de Habilidades (`RF-EVA`)

| ID | Requisito Funcional | Prioridad |
|---|---|:---:|
| **RF-EVA-01** | El usuario podrá solicitar formalmente la validación de una habilidad que ofrece. | A |
| **RF-EVA-02** | El sistema estructurará la evaluación articulando una fase teórica y una fase práctica específica según la disciplina. | A |
| **RF-EVA-03** | La evaluación teórica seleccionará aleatoriamente reactivos del banco (opción múltiple, V/F, respuesta corta) según nivel. | A |
| **RF-EVA-04 ★** | **Evaluación adaptativa (CAT)**: la dificultad de los reactivos se calibrará en tiempo real según las respuestas previas para maximizar precisión con menor número de ítems. | M |
| **RF-EVA-05** | **Programación**: editor de código integrado en navegador con compilación/ejecución en contenedor aislado (*sandbox*) y suites de pruebas unitarias automáticas. | A |
| **RF-EVA-06** | Análisis estático del código del usuario: parsing a AST, métricas de complejidad ciclomática, eficiencia algorítmica y buenas prácticas. | A |
| **RF-EVA-07 ★** | **Defensa de la solución**: el sistema formulará preguntas contextuales derivadas del AST generado (plantillas parametrizadas sin LLM); el usuario responderá por texto y un clasificador local contrastará conceptos clave. | M |
| **RF-EVA-08 ★** | Detección de plagio de código: análisis de similitud estructural de AST con base de conocimiento, soluciones históricas y detección de patrones de tipeo/pegado. | M |
| **RF-EVA-09** | **Instrumentos musicales**: solicitud de ejecución en vivo de ejercicios específicos (escalas, progresiones de acordes, piezas guiadas) frente a cámara y micrófono. | A |
| **RF-EVA-10** | Análisis acústico con librosa/PyTorch sobre espectrogramas: evaluación de afinación (pitch detection), tempo/ritmo, limpieza armónica y dinámica. | A |
| **RF-EVA-11** | Análisis visual musical: modelo de visión entrenado que valida presencia del instrumento correspondiente y postura/técnica de ejecución de manos. | M |
| **RF-EVA-12** | **Fútbol / Deportes**: desafíos motrices y técnicos (dominadas, control orientado, conducción, pases a diana) registrados por cámara. | A |
| **RF-EVA-13** | Modelo de visión deportiva: estimación de pose corporal y tracking de balón para cómputo de repeticiones, estabilidad, control y precisión del gesto. | A |
| **RF-EVA-14** | Instrucciones previas detalladas con videos demostrativos y cuenta regresiva de preparación antes de cada desafío práctico. | A |
| **RF-EVA-15** | Control de pausas: solo permitidas en puntos de control autorizados, con auditoría de tiempo transcurrido. | M |
| **RF-EVA-16** | Resiliencia ante desconexiones: guardado de estado transaccional para reanudar dentro de una ventana máxima de gracia. | M |
| **RF-EVA-17** | Motor de puntuación compuesto: consolidación ponderada de scores de modelos prácticos y examen teórico. | A |
| **RF-EVA-18** | Asignación automática de nivel y otorgamiento de sello de certificación si se supera el umbral del corte establecido. | A |
| **RF-EVA-19 ★** | **Entrenador de IA con feedback formativo**: reporte comprensivo de fortalezas, errores técnicos y recomendaciones de mejora generado por reglas/plantillas sobre métricas duras (sin IA generativa). | M |
| **RF-EVA-20** | Período de enfriamiento (*cooldown*) y límite de intentos ante evaluaciones no aprobadas. | A |
| **RF-EVA-21** | Flujo de apelación y solicitud de revisión manual por evaluadores humanos autorizados. | M |
| **RF-EVA-22** | Histórico integral de evaluaciones, métricas obtenidas y evolución de niveles del usuario. | A |
| **RF-EVA-23** | Modo de simulación/práctica libre sin impacto en la certificación formal. | B |
| **RF-EVA-24** | Medición de confianza de la inferencia (*confidence score*); derivación automática a revisión humana si el score de confianza es inferior al umbral mínimo. | M |

---

### 3.4 Módulo 4 – Búsqueda, Matching e Intercambio (`RF-MAT`)

| ID | Requisito Funcional | Prioridad |
|---|---|:---:|
| **RF-MAT-01** | Búsqueda paramétrica de instructores por habilidad ofrecida. | A |
| **RF-MAT-02** | Filtros multidimensionales: habilidad, nivel, sello de verificación, modalidad, distancia geográfica, disponibilidad, idioma y rating. | A |
| **RF-MAT-03** | Motor de coincidencia bidireccional (*bilateral matching*): correlación exacta entre oferta y demanda mutua ($A \leftrightarrow B$). | A |
| **RF-MAT-04** | Algoritmo de cálculo de compatibilidad (%) basado en matriz de pesos (habilidades, niveles, disponibilidad horaria, ubicación e idioma). | A |
| **RF-MAT-05** | Renderizado de *Match Card* detallando habilidades complementarias, sellos de verificación y score de afinidad. | A |
| **RF-MAT-06** | Explicabilidad del match: desglose legible de las variables que motivan la compatibilidad sugerida. | M |
| **RF-MAT-07** | Flujo de invitación: aceptar, declinar o guardar; formalización del intercambio tras aceptación mutua. | A |
| **RF-MAT-08 ★** | **Matching multilateral en cadena**: resolución de ciclos de intercambio para 3 o más participantes ($A \to B \to C \to A$) cuando no hay reciprocidad directa. | M |
| **RF-MAT-09 ★** | **Matching unilateral con Banco de Tiempo**: compensación basada en créditos de tiempo cuando el intercambio no es simétrico. | M |
| **RF-MAT-10** | Sugerencias automáticas diarias de perfiles afines según hábitos de búsqueda y perfiles actualizados. | M |
| **RF-MAT-11** | Priorización algorítmica de usuarios verificados y filtro exclusivo de instructores con sello certificado. | A |
| **RF-MAT-12** | Guardado de búsquedas frecuentes con alertas automáticas ante nuevas incorporaciones compatibles. | B |
| **RF-MAT-13** | Ajuste adaptativo del motor de recomendación en función de patrones de aceptación y rechazo del usuario. | B |
| **RF-MAT-14** | Bloqueo y reporte de perfiles, con exclusión inmediata de resultados de búsqueda y sugerencias. | A |
| **RF-MAT-15** | Búsqueda por proximidad con radio difuso (geolocalización aproximada para proteger privacidad domiciliaria). | M |
| **RF-MAT-16 ★** | **Radar de oportunidades**: panel analítico que informa qué habilidades presentan mayor déficit de oferta y sugiere qué aprender para maximizar matches. | B |

---

### 3.5 Módulo 5 – Supervisión y Prevención de Fraude (`RF-FRA`)

| ID | Requisito Funcional | Prioridad |
|---|---|:---:|
| **RF-FRA-01** | Banco aleatorio de preguntas y retos para evitar filtraciones y repeticiones sistemáticas. | A |
| **RF-FRA-02** | Timeouts estrictos configurables por ítem y por evaluación general. | A |
| **RF-FRA-03** | Detección de pérdida de foco, cambio de pestaña y salida de modo pantalla completa con logging de eventos. | A |
| **RF-FRA-04** | Monitoreo continuo de cámara y notificación/pausa ante corte de señal o desconexión intencional. | A |
| **RF-FRA-05** | Detección de múltiples rostros en simultáneo mediante OpenCV/red convolucional propia, emitiendo alertas de incidencia. | A |
| **RF-FRA-06** | Detección de voces adicionales y susurros externos en evaluaciones orales/musicales (análisis espectral y VAD). | M |
| **RF-FRA-07** | Prueba de vida (*liveness*): verificación de sujeto vivo mediante órdenes motoras aleatorias (parpadeo, giro de cabeza, gesticulación). | A |
| **RF-FRA-08** | Chequeo de entorno pre-evaluación: calibración de iluminación, funcionamiento de periféricos, encuadre facial y calidad de enlace. | A |
| **RF-FRA-09** | Bloqueo de acciones de portapapeles (copiar, pegar, corte, atajos de teclado y menú contextual) en el entorno de evaluación. | A |
| **RF-FRA-10 ★** | **Verificación de identidad continua**: cotejo biométrico periódico del rostro durante la prueba contra la foto testigo inicial para impedir suplantación durante la sesión. | M |
| **RF-FRA-11** | Detección de desvío ocular persistente fuera del área del monitor. | B |
| **RF-FRA-12** | Detección de pantallas compartidas, máquinas virtuales o drivers virtuales de captura cuando el navegador lo reporte. | B |
| **RF-FRA-13** | Detección de video pregrabado (loops de cámara virtual) mediante análisis de ruido de sensor y consistencia temporal. | M |
| **RF-FRA-14** | Cálculo de puntaje global de riesgo de la evaluación según gravedad acumulada de anomalías registradas. | A |
| **RF-FRA-15** | Sistema escalonado de respuestas: advertencia en pantalla, penalización, invalidación de prueba o derivación a tribunal de auditoría. | A |
| **RF-FRA-16** | Bitácora de supervisión forense inmutable con marcas de tiempo, capturas de pantalla y telemetría de eventos. | A |
| **RF-FRA-17** | Consola de auditoría para que administradores examinen evidencia y ratifiquen o anulen sanciones. | A |
| **RF-FRA-18** | Mecanismo formal de apelación con descargo justificado por parte del usuario. | M |
| **RF-FRA-19** | Transparencia con el usuario: advertencia previa de los mecanismos de monitoreo y opción de cancelación antes de iniciar. | A |
| **RF-FRA-20** | Cumplimiento de privacidad: política estricta de retención y borrado definitivo de telemetría y grabaciones tras dictamen de validación. | A |

---

### 3.6 Módulo 6 – Inteligencia Artificial y Administración de Datasets (`RF-IA`)

| ID | Requisito Funcional | Prioridad |
|---|---|:---:|
| **RF-IA-01** | Módulo de gestión y versionado de datasets de entrenamiento categorizados por habilidad. | A |
| **RF-IA-02** | Herramienta de etiquetado interno de datos (muestras de video, pistas de audio, fragmentos de código) con anotaciones periciales. | A |
| **RF-IA-03** | Validadores de integridad y calidad de datasets (balance de clases, remoción de duplicados, saneamiento de formatos corruptos). | M |
| **RF-IA-04** | Modelo de Fútbol: red propia sobre video para tracking de balón, keypoints corporales y clasificación técnica del gesto. | A |
| **RF-IA-05** | Modelo de Instrumentos: procesamiento espectral y red convolucional propia para evaluación de tono, ritmo y técnica gestual. | A |
| **RF-IA-06** | Modelo de Programación: combinatoria de parser AST, cálculo de métricas de software y clasificador propio de respuestas conceptuales (sin LLM). | A |
| **RF-IA-07** | Estandarización de salida: cada modelo produce métricas normalizadas y score de confiabilidad estadística. | A |
| **RF-IA-08** | Interfaz de administración para lanzamiento, monitoreo y comparación de entrenamientos (curvas de pérdida, accuracy, F1-score). | M |
| **RF-IA-09** | Gestión de versiones de modelos en producción con capacidad de rollback inmediato. | M |
| **RF-IA-10** | Gestión administrativa del banco de ítems teóricos y desafíos prácticos por nivel y disciplina. | A |
| **RF-IA-11 ★** | **Pipeline de aprendizaje continuo supervisado**: incorporación de evaluaciones dudosas o revisadas manualmente a los sets de reentrenamiento previa anonimización y consentimiento. | M |
| **RF-IA-12 ★** | Generación de variantes de ejercicios a partir de plantillas parametrizadas con validación previa de administrador. | B |
| **RF-IA-13** | Dashboard de métricas de calidad de inferencia (matrices de confusión, tasas de falsos positivos/negativos y análisis de sesgos). | M |
| **RF-IA-14** | Arquitectura desacoplada y modular que permite acoplar evaluadores para nuevas habilidades sin alterar el core del backend. | M |
| **RF-IA-15** | Registro inmutable de metadata de inferencia (versión del modelo, hiperparámetros y pesos usados) por cada evaluación. | A |

---

### 3.6.1 Requisitos Adicionales de IA Propia (`RF-IA-EXT`)

| ID | Requisito Funcional | Prioridad |
|---|---|:---:|
| **RF-IA-16** | Ejecución 100% *on-premise* o en VPS privado: ningún dato personal, código o multimedia es transmitido a servicios de IA de terceros. | A |
| **RF-IA-17** | Inventario exhaustivo y versionado de librerías, dependencias y modelos base autorizados con detalle de licencia y propósito. | A |
| **RF-IA-18** | Módulo de captura de datos multiplataforma (web/móvil) para grabación controlada de muestras de entrenamiento con consentimiento. | A |
| **RF-IA-19** | Protocolo de doble ciego en etiquetado: cada muestra requiere anotación independiente de al menos dos evaluadores para medir concordancia inter-anotador (Cohen's Kappa). | M |
| **RF-IA-20** | Extracción estructurada de features específicas por habilidad (ej. toques/minuto, error cuadrático de afinación, complejidad ciclomática). | A |
| **RF-IA-21** | Protocolo formal de validación de modelos con particiones estrictas (Train / Validation / Test) y reporte de métricas científicas. | A |
| **RF-IA-22** | Estrategia de arranque en frío (*cold start*): evaluación mediante heurísticas y reglas duras calibradas mientras se recolecta el dataset suficiente para la convergencia del modelo neuronal. | A |
| **RF-IA-23** | Motor determinístico de feedback y preguntas de defensa basado en árboles de decisión y plantillas parametrizadas (garantizando ausencia de alucinaciones de LLMs). | M |

---

### 3.7 Módulo 7 – Sesiones de Intercambio (`RF-SES`)

| ID | Requisito Funcional | Prioridad |
|---|---|:---:|
| **RF-SES-01** | Chat de texto en tiempo real habilitado entre usuarios tras aceptación recíproca de coincidencia. | A |
| **RF-SES-02** | Gestión de sesiones: proponer, coordinar, aceptar, reprogramar y cancelar encuentros con fijación de fecha, hora y modalidad. | A |
| **RF-SES-03** | Negociación horaria asistida: recomendación automática de huecos de agenda comunes según disponibilidad y husos horarios. | A |
| **RF-SES-04** | Soporte para sesiones virtuales con integración de sala de videoconferencia, pizarra digital colaborativa y pantalla compartida. | M |
| **RF-SES-05** | Seguridad en encuentros presenciales: sugerencia de espacios públicos neutrales y función de compartir trayecto de seguridad con contacto externo. | M |
| **RF-SES-06** | Sistema de recordatorios transaccionales programados por push y correo electrónico previo a las sesiones. | A |
| **RF-SES-07** | Protocolo de cierre: confirmación dual de realización efectiva de la sesión y cómputo de horas impartidas/recibidas. | A |
| **RF-SES-08 ★** | **Banco de Tiempo**: monedero de créditos de tiempo (1 hora enseñada = 1 crédito de aprendizaje) para posibilitar intercambios asimétricos. | M |
| **RF-SES-09 ★** | **Plan de sesión asistido**: formulación automática de temarios, metas pedagógicas y dinámicas sugeridas según el nivel del aprendiz (basado en plantillas). | M |
| **RF-SES-10 ★** | **Resumen estructurado post-sesión**: consolidación automática de apuntes, acuerdos y asignaciones mediante plantillas predefinidas. | B |
| **RF-SES-11** | Registro y seguimiento de asignaciones prácticas o lecturas entre sesiones consecutivas. | B |
| **RF-SES-12** | Penalización automática de reputación ante inasistencias injustificadas (*no-shows*). | M |
| **RF-SES-13** | Canal inmediato para reporte de incidentes y conducta inapropiada durante o post sesión. | A |
| **RF-SES-14** | Calendario personal del usuario con vista de sesiones programadas, solicitudes pendientes e historial. | A |
| **RF-SES-15** | Exportación y sincronización de eventos de intercambio con Google Calendar e iCalendar. | B |

---

### 3.8 Módulo 8 – Reputación, Confianza y Gamificación (`RF-REP`)

| ID | Requisito Funcional | Prioridad |
|---|---|:---:|
| **RF-REP-01** | Sistema de calificación bilateral post-encuentro (evaluación cuantitativa 1-5 estrellas y feedback cualitativo en puntualidad, pedagogía y solvencia). | A |
| **RF-REP-02 ★** | **Puntaje de Confianza Dinámico**: algoritmo de reputación multidimensional que pondera verificaciones superadas, ratio de fraude, feedback de pares, asistencia e historial. | M |
| **RF-REP-03** | Exhibición destacada de insignias de verificación de competencias y reconocimientos de actividad en el perfil. | A |
| **RF-REP-04 ★** | **Verificación por Pares Calificados**: habilitación a usuarios con nivel Experto validado para actuar como jurados de segundo nivel en evaluaciones prácticas dudosas. | B |
| **RF-REP-05 ★** | **Ruta de Aprendizaje Personalizada**: visualización interactiva de objetivos cumplidos, habilidades en proceso y brecha hacia el nivel meta. | M |
| **RF-REP-06** | Sistema de logros e insignias por hitos de compromiso (primera clase, 10 horas completadas, tutor confiable, habilidad de oro). | B |
| **RF-REP-07** | Moderación de comentarios ofensivos y filtros de lenguaje inadecuado en las reseñas públicas. | M |
| **RF-REP-08** | Detección heurística de colusión (reseñas recíprocas falsas o cuentas infladas artificialmente). | B |
| **RF-REP-09** | Derecho a réplica: el usuario valorado podrá publicar una respuesta formal a las evaluaciones recibidas en su perfil. | B |

---

### 3.9 Módulo 9 – Notificaciones, Comunicación y Administración General (`RF-NOT`)

| ID | Requisito Funcional | Prioridad |
|---|---|:---:|
| **RF-NOT-01** | Bus de eventos y notificaciones en tiempo real vía WebSockets (matches inmediatos, mensajes directos, alertas de sesión y resoluciones de validación). | A |
| **RF-NOT-02** | Notificaciones por correo electrónico transaccional (confirmaciones de cuenta, restablecimiento de contraseñas, citaciones). | A |
| **RF-NOT-03** | Centro de preferencias de usuario para configuración granular de canales de notificación (push, email, in-app). | M |
| **RF-NOT-04** | Indicador de estado de procesamiento asíncrono para evaluaciones en etapa de cómputo por los evaluadores de IA. | A |
| **RF-NOT-05** | Dashboard de analítica administrativa: usuarios activos, volumen de intercambios, demanda de habilidades, tasas de éxito y métricas de fraude. | M |
| **RF-NOT-06** | Centro de resolución de denuncias para moderadores con trazabilidad de penalizaciones y sanciones. | A |
| **RF-NOT-07** | Registro de auditoría del sistema (*audit log*) inmutable para acciones de administradores y cambios en configuraciones sensibles. | A |
| **RF-NOT-08** | Soporte de internacionalización (i18n): localización en español e inglés. | B |
| **RF-NOT-09** | Gestión de permisos nativos en cliente móvil (Capacitor) para acceso autorizado a cámara, micrófono y notificaciones push. | A |

---

## 4. Trazabilidad con el Alcance Original

| Módulo del Alcance | Requisitos Mapeados | Total RF |
|---|---|:---:|
| Módulo 1 – Usuarios y Accesos | `RF-USR-01` a `RF-USR-17` | 17 |
| Módulo 2 – Gestión de Habilidades | `RF-HAB-01` a `RF-HAB-13` | 13 |
| Módulo 3 – Evaluación y Validación | `RF-EVA-01` a `RF-EVA-24` | 24 |
| Módulo 4 – Búsqueda y Matching | `RF-MAT-01` a `RF-MAT-16` | 16 |
| Módulo 5 – Supervisión y Fraude | `RF-FRA-01` a `RF-FRA-20` | 20 |
| Módulo 6 – IA y Datasets (Base + IA Propia) | `RF-IA-01` a `RF-IA-23` | 23 |
| Módulo 7 – Sesiones de Intercambio | `RF-SES-01` a `RF-SES-15` | 15 |
| Módulo 8 – Reputación, Confianza y Gamificación | `RF-REP-01` a `RF-REP-09` | 9 |
| Módulo 9 – Notificaciones y Administración | `RF-NOT-01` a `RF-NOT-09` | 9 |
| **Total Requisitos Funcionales** | | **146** |

---

## 5. Planificación y Priorización por Sprints (Roadmap Técnico)

| Sprint | Foco Principal del Incremento | Requisitos Clave Abordados |
|:---:|---|---|
| **Sprint 1** | **Fundación & Autenticación (MVP Core)** | `RF-USR` (Prioridad A): Registro, login con JWT, perfiles, roles y disponibilidad. |
| **Sprint 2** | **Catálogo & Ingesta de Habilidades** | `RF-HAB` (A): Taxonomía de habilidades, habilidades que enseño/deseo, estados. Herramienta de captura de datasets (`RF-IA-18`, `RF-IA-19`). |
| **Sprint 3** | **Búsqueda & Matching Bidireccional** | `RF-MAT` (A) y `RF-NOT` básicos: Motor de compatibilidad $A \leftrightarrow B$, WebSockets básicos y match cards. |
| **Sprint 4** | **Evaluación de Programación & Anti-Fraude Base** | `RF-EVA` (A) y `RF-FRA` (A) para código: Sandbox de ejecución, AST, métricas de código, liveness y bloqueo de portapapeles. |
| **Sprint 5** | **Evaluación de Música & Fútbol (Modelos IA)** | `RF-IA`, `RF-EVA` y `RF-FRA`: Detección de pose, tracking de balón, análisis con librosa/PyTorch y monitoreo de múltiples rostros/voces. |
| **Sprint 6** | **Sesiones, Confianza & Pasaporte** | `RF-SES` y `RF-REP` (A/M): Agendamiento de sesiones, calificaciones recíprocas y Pasaporte de Habilidades con QR (`RF-HAB-11`). |
| **Sprint 7** | **Diferenciadores Avanzados & Consolidación** | Matching multilateral en cadena (★2), Banco de Tiempo (★7), Defensa de solución (★5) y reentrenamiento supervisado. |

---

## 6. Criterios de Implementación y Alcance Realista

1. **Definición de MVP (Producto Mínimo Viable):**
   - El MVP abarca el 100% de los requisitos con **Prioridad A**, más dos a tres diferenciadores clave seleccionados (Matching multilateral, feedback del Entrenador de IA y Puntaje de Confianza).
   - Los requisitos de prioridad **M** y **B** se integran de forma progresiva según la cadencia de los sprints.
2. **Prioridad Crítica del Modelo de Programación:**
   - Al no depender inicialmente de captura física masiva de video/audio en campo, la evaluación de **programación** es el primer motor completo a certificar (sandbox, AST y análisis estático).
3. **Estrategia para Modelos de Música y Fútbol:**
   - La recolección de datasets propios es el camino crítico. La herramienta de captura y etiquetado (`RF-IA-18`, `RF-IA-19`) debe estar operativa desde el Sprint 2 para nutrir los datasets mientras se consolidan los sprints 3 y 4.
