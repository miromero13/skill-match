# Plan de implementación: validación de habilidades y anticopia compartido

Este plan organiza un flujo común para validar cualquier habilidad: preparar la evaluación, comprobar el ambiente y la identidad, rendir tres etapas con supervisión y obtener un dictamen. La práctica de programación está a tu cargo; las prácticas de guitarra y deportes están a cargo de otras personas, pero deben integrarse al mismo flujo y al mismo anticopia.

**Estado:** plan acordado para orientar la implementación. No acredita que las funcionalidades ya estén implementadas ni verificadas.

## 1. Objetivo y alcance

Un miembro debe poder solicitar la validación de una habilidad que ofrece, rendir una evaluación supervisada y recibir un resultado con feedback y, si corresponde, un sello de habilidad verificada.

### Las tres etapas son las mismas para todas las habilidades

| Etapa | Funcionamiento compartido | Qué cambia según la habilidad |
|---|---|---|
| 1. Teoría | Presentar preguntas, controlar tiempos, guardar respuestas y calificarlas | Banco de preguntas y contenido: programación, guitarra, deporte u otra habilidad |
| 2. Práctica | Presentar la consigna, recibir la entrega y registrar su resultado en el mismo intento | Actividad, captura y evaluador: sandbox de código, ejecución musical o ejercicio deportivo |
| 3. Defensa con preguntas | Preguntar sobre lo realizado, recibir explicaciones y comprobar comprensión | Preguntas y reglas de evaluación vinculadas a la habilidad y a la evidencia práctica |

**Teoría y defensa se construyen una sola vez como mecanismos comunes.** No significa hacer las mismas preguntas de programación a alguien que valida guitarra. Cambian los contenidos, no se duplica el flujo. En la práctica sí cambia la actividad y su procesamiento especializado.

**El anticopia es común y permanece activo en las tres etapas**, sin importar la habilidad. Incluye preparación del ambiente, verificación de identidad, controles del navegador, supervisión, bitácora y revisión de incidentes. La similitud AST es un control adicional específico de código, no la base del anticopia compartido.

### Relación con tus tareas de Jira

| Jira | Responsabilidad y alcance |
|---|---|
| SM-23 | Instrucciones, elegibilidad y consentimiento comunes |
| SM-44 | Ambiente, calibración, prueba de vida y cotejo facial inicial comunes |
| SM-43 | Control de foco, pestañas y portapapeles; bitácora común |
| SM-49 | Supervisión continua común de presencia, identidad y señales de audio |
| SM-39 | Mecanismo común de teoría y tiempos; la redacción actual se centra en programación |
| SM-40 | Práctica específica de programación: editor y sandbox |
| SM-41 | Análisis específico de programación: AST, complejidad y calidad |
| SM-42 | Mecanismo común de defensa; la redacción actual cubre preguntas derivadas del AST de código |
| SM-45 | Cierre común de la evaluación; integrar resultados según la disciplina |
| SM-46 | Auditoría y apelaciones comunes a todas las validaciones |

**Alinear Jira antes de implementar el alcance ampliado:** SM-39 y SM-42 deben explicitar su mecanismo compartido y separar el contenido específico de programación. Las prácticas de guitarra y deportes, SM-47 y SM-48, quedan a cargo de otras personas; no deben duplicar teoría, defensa ni anticopia. Este documento define el flujo acordado, pero no modifica Jira ni da por implementado ese soporte.

**Pendiente de explicitar en Jira:** la comparación estructural de código con soluciones de referencia e históricas requerida por RF-EVA-08. No debe darse por cubierta solamente con SM-41 ni con el bloqueo del portapapeles. Su tarea o sus criterios deben acordarse antes de implementarla.

## 2. Qué debe existir antes de comenzar

El miembro ya debe tener:

- Una cuenta autenticada con Google y rol `MEMBER`.
- Su perfil creado.
- Su rostro biométrico registrado mediante el enrolamiento del perfil.
- Una habilidad que enseña, todavía sin verificar. Python será el ejemplo para desarrollar e integrar tu práctica de programación.

El catálogo debe contener esa habilidad activa y asociada al tipo de desafío correspondiente. El usuario debe estar habilitado para solicitar un intento según las reglas de cupos y bloqueos aplicables.

Para preparar el primer escenario con Python, seguir [Preparar manualmente la validación de programación](manual-programming-setup.md). La guía carga un ejemplo de integración, no restringe el flujo común a programación. No ejecutar cargas automáticas ni agregar resultados, sanciones o certificados ficticios para saltarse el recorrido.

### Dos distinciones importantes

- **Habilidad ofrecida no es habilidad verificada:** el miembro declara que puede enseñarla; la evaluación certifica su nivel.
- **Enrolamiento no es verificación inicial del examen:** el perfil conserva la referencia facial; al comenzar se comprueba que quien está presente corresponde a esa referencia y supera la prueba de vida.

**Punto de entrada:** Mis habilidades → Python → Validar habilidad.

## 3. Flujo del usuario y comportamiento del sistema

### Paso 1. Ver instrucciones y aceptar las condiciones — SM-23

**El usuario ve:**

- Qué se evaluará y qué etapas tendrá la prueba.
- Duración y requisitos: cámara, micrófono y ambiente adecuado.
- Reglas de integridad y acciones no permitidas.
- Cupos e intentos disponibles.
- Explicación del uso de cámara, micrófono y procesamiento biométrico.

**El sistema:** valida la habilidad ofrecida, su pertenencia al miembro, el enrolamiento y la elegibilidad; registra el consentimiento y su versión de política.

**Criterio de cierre:** no se puede avanzar a la comprobación con cámara ni iniciar el examen sin consentimiento. La restricción debe existir en backend, no solamente en el botón del frontend.

### Paso 2. Comprobar el ambiente y la identidad — SM-44 + integración con SM-49

Esta etapa ocurre **antes de mostrar preguntas o empezar el examen**. El usuario ve su cámara y una lista de comprobaciones.

| Comprobación | Qué debe comprobar el sistema |
|---|---|
| Cámara | Está disponible y entrega imagen |
| Micrófono | Tiene permiso y recibe audio |
| Iluminación | Permite observar el rostro |
| Encuadre | El rostro se ve suficientemente bien |
| Presencia | Hay una sola persona visible |
| Identidad | El rostro corresponde al registrado en el perfil |
| Prueba de vida | Se cumple un movimiento aleatorio solicitado en ese momento |

Si una condición falla, la interfaz explica qué corregir. Ejemplos de indicaciones propuestas:

> Hay poca luz. Mejorá la iluminación para continuar.

> Ubicá tu rostro dentro del encuadre.

SM-44 cubre la calibración y verificación inicial. La detección de presencia de SM-49 se reutiliza para comprobar una sola persona al inicio y después mantener la supervisión; esta integración debe quedar explícita en los criterios correspondientes.

**Criterio de cierre:** el usuario puede corregir su ambiente y repetir la comprobación, pero no habilitar el examen mientras falle una condición obligatoria. Tampoco puede saltarse la etapa mediante una llamada directa a la API.

**Límite técnico:** la cámara permite comprobar condiciones observables, no garantizar que toda la habitación esté libre de ayuda. Un nombre de dispositivo tampoco garantiza que la cámara sea física. No presentar estas heurísticas como garantías absolutas.

### Paso 3. Comenzar la evaluación y activar el anticopia — SM-43 + SM-49

Una vez aprobada la preparación, el usuario presiona **Comenzar evaluación**. Desde ese momento, la supervisión acompaña las partes evaluables.

| Parte del anticopia | Qué controla | Responsable |
|---|---|---|
| Navegador | Cambio de pestaña, pérdida de foco, copiar, pegar y cortar | SM-43 |
| Supervisión audiovisual | Ausencia del usuario, aparición de otra persona, cambios de identidad y señales de audio que requieren revisión | SM-49 |
| Comprensión de la práctica | Defensa con preguntas sobre lo realizado en cualquier habilidad | Mecanismo compartido de SM-42, con contenido por habilidad |
| Control adicional de código | Similitud estructural con otras soluciones de programación | RF-EVA-08 explícito, específico de programación |

Ante un problema, el sistema registra qué ocurrió y cuándo, muestra el aviso correspondiente y aplica la acción acordada: advertir, pausar o derivar a revisión. Las sanciones se implementan únicamente después de definir su política.

**Criterio de cierre:** los incidentes quedan asociados al intento correcto, una misma acción no se cuenta dos veces y los controles se liberan al salir de la evaluación.

**No confundir señales con fraude confirmado:** un corte de cámara puede ser una falla técnica; la actividad de voz detectada por VAD no identifica por sí sola a una persona distinta. El mismo supervisor debe conocer la etapa y actividad: el sonido de una guitarra, una respuesta oral o el movimiento esperado en un reto deportivo no son por sí mismos una infracción. Ajustar parámetros por actividad no significa construir otro anticopia.

### Paso 4. Rendir la teoría común — SM-39

**El usuario:** responde preguntas correspondientes a la habilidad que está validando, con tiempo limitado. Quien valida guitarra también realiza esta etapa.

**El sistema:** usa el mismo mecanismo para seleccionar preguntas por habilidad y nivel, guardar respuestas, controlar tiempos desde el backend y calificar. SM-43 y SM-49 permanecen activos. Recargar no debe cambiar las preguntas del intento ni reiniciar el reloj.

**Criterio de cierre:** el mecanismo permite cambiar de banco de preguntas sin duplicar pantallas ni lógica. Quedan persistidos respuestas, tiempos e incidentes; la API no expone respuestas correctas antes de tiempo y rechaza envíos fuera del plazo.

### Paso 5. Realizar la práctica específica de la habilidad

**El usuario:** recibe una consigna y realiza la actividad correspondiente. Esta es la etapa cuya ejecución cambia según la habilidad.

| Habilidad | Práctica | Responsabilidad |
|---|---|---|
| Programación | Escribir código, ejecutar pruebas y entregar la solución | Tu implementación: SM-40 y análisis SM-41 |
| Guitarra | Realizar y registrar la ejecución musical solicitada | Otra persona: integración con SM-47 |
| Deportes | Realizar y registrar el ejercicio físico solicitado | Otra persona: integración con SM-48 |

**El sistema común:** mantiene el mismo intento y la supervisión de SM-43 y SM-49, y recibe la evidencia y el resultado del evaluador correspondiente. No crea un examen independiente por disciplina.

**Tu parte de programación:** ejecutar el código en un sandbox aislado con límites de recursos y tiempo, guardar resultados y fijar la entrega final. Los bucles infinitos terminan por timeout y los tests privados no se exponen.

**Criterio de cierre de integración:** cada práctica entrega evidencia y resultados identificables para la defensa y el cierre comunes, sin implementar otro consentimiento, otra teoría u otro anticopia. La implementación interna de guitarra y deportes no forma parte de tu trabajo.

### Paso 6. Comprobar comprensión mediante defensa común — SM-42

**El usuario:** responde preguntas sobre la práctica realizada. Esta tercera etapa existe para todas las habilidades, no solamente para programación.

**El sistema común:** presenta las preguntas correspondientes, recibe respuestas, controla el tiempo, guarda la evaluación y mantiene activo el mismo anticopia. Las preguntas y reglas son locales y determinísticas, sin servicios externos de IA.

**Lo específico de programación:** las preguntas se obtienen de la entrega final mediante su AST. SM-41 aporta métricas de calidad y complejidad; RF-EVA-08 aporta señales adicionales de similitud cuando se explicite su alcance. Los tests de SM-40 comprueban funcionamiento: ninguno de estos resultados sustituye a los otros.

**Lo específico de guitarra y deportes:** sus responsables deben acordar y aportar el contenido o las reglas de preguntas vinculadas a la práctica. No se intenta analizar audio o movimientos con el AST de Python ni se afirma que la historia actual ya cubre ese contenido.

**Criterio de cierre:** teoría y defensa son mecanismos distintos pero ambos reutilizables entre habilidades; la defensa referencia la evidencia práctica correcta. En programación, métricas y similitud son reproducibles y una solución corta o común no se declara automáticamente fraudulenta por parecerse a otra.

### Paso 7. Mostrar el resultado — SM-45

**El usuario ve:** resultado, desglose, fortalezas, aspectos a mejorar y, cuando corresponda, nivel y sello.

**El sistema:** consolida los resultados de teoría, práctica y defensa, y considera el estado de integridad del intento según la política acordada. El cierre es compartido; las métricas prácticas provienen del evaluador de cada habilidad.

**Para programación, Jira define:** teoría 30 %, código 50 %, AST/defensa 20 %. No aplicar automáticamente esa fórmula ni métricas AST a guitarra y deportes: sus ponderaciones y rúbricas deben quedar acordadas con los responsables correspondientes.

| Salida | Efecto esperado |
|---|---|
| Aprobado | Se otorga la certificación correspondiente |
| No aprobado | Se muestra feedback sin otorgar certificación |
| Pendiente de revisión | Se espera el dictamen antes de resolver la certificación |

**Criterio de cierre:** resultado y sello corresponden al dictamen real. Repetir la finalización no duplica certificados ni aplica efectos varias veces.

### Paso 8. Revisar incidentes y apelaciones — SM-46

El administrador consulta la evidencia relevante y registra una decisión. El usuario puede presentar una apelación según las condiciones definidas.

**Criterio de cierre:** las alertas tienen evidencia revisable, los dictámenes quedan registrados y sus efectos son consistentes con la evaluación y la certificación. Los accesos no autorizados a rutas administrativas respetan la política 404 del proyecto.

## 4. Orden de implementación

El recorrido funcional anterior se construye en este orden. Cada entrega incluye backend, integración frontend y pruebas; no se separa el trabajo en una fase de todas las pantallas y otra de toda la lógica.

| Orden | Trabajo | Demostración para darlo por terminado |
|---|---|---|
| 1 | SM-23: instrucciones, elegibilidad y consentimiento | Sin aceptar condiciones no se avanza |
| 2 | SM-44: ambiente, prueba de vida e identidad; integrar presencia de SM-49 | El usuario corrige su ambiente y solo continúa al superar los controles |
| 3 | SM-43: bitácora y control del navegador | Un cambio de pestaña registra un único incidente y el aviso acordado |
| 4 | SM-49: supervisión continua | Ausencia, múltiples personas y señales de identidad alimentan la bitácora y la respuesta acordada |
| 5 | SM-39: teoría común supervisada | Cambiar de habilidad cambia las preguntas, no duplica el motor de teoría |
| 6 | Contrato de práctica común + SM-40 | Tu sandbox se integra al intento; responsables de SM-47/48 conocen cómo conectar sus prácticas |
| 7 | SM-41 + alcance explícito de similitud de código | Se obtienen métricas y señales específicas de programación sin mezclarlas con el supervisor común |
| 8 | SM-42: defensa común y preguntas por habilidad | El mismo flujo permite defender prácticas distintas; tu integración genera preguntas por AST |
| 9 | SM-45: cierre común, resultado y sello | Se consumen resultados de cada habilidad sin imponerles métricas de código ni duplicar certificados |
| 10 | SM-46: auditoría y apelación comunes | El administrador revisa casos de cualquier habilidad mediante la misma bitácora |

**No esperar a tener teoría y sandbox completos para empezar el anticopia.** Primero probar la preparación y supervisión en una pantalla de prueba; después integrarlas al examen. Esa pantalla sirve para desarrollar y verificar el control, no para introducir una nueva funcionalidad de producto.

### Reglas compartidas que deben acordarse antes de implementar sus efectos

- Momento exacto de consumo de un intento y tratamiento de fallas durante la preparación.
- Política de desconexión, pausa y eventual reanudación.
- Eventos que producen advertencia, pausa, revisión o sanción; evitar dobles conteos.
- Condición para pasar de teoría a práctica y umbrales de aprobación.
- Correspondencia entre los cinco niveles del catálogo actual y los niveles del dictamen.
- Alcance, referencias y criterios de la comparación de similitud RF-EVA-08, específica de código.
- Contenido por habilidad de las dos etapas compartidas: teoría y defensa; alinear SM-39 y SM-42 con este alcance.
- Evidencia y resultados que deben entregar las prácticas de guitarra y deportes al flujo común, sin asumir su implementación ni sus ponderaciones.

Todo el recorrido debe pertenecer al mismo intento: cambiar de etapa no crea evaluaciones independientes ni vuelve a descontar cupos. También deben corregirse los enlaces de bloqueo de Jira que contradicen el orden consentimiento → calibración → examen, incluido el ciclo detectado entre SM-40 y SM-44.

## 5. Cómo trabajar y cerrar cada tarea

1. Revisar sus criterios y confirmar dependencias.
2. Escribir primero las pruebas de las reglas verificables, usando estado aislado y no la base local de trabajo.
3. Implementar el contrato y las restricciones en backend.
4. Integrar el frontend y mostrar textualmente el `message` recibido del backend.
5. Verificar el recorrido real y su comportamiento responsive.
6. Registrar la evidencia antes de marcar la tarea como terminada.

No cerrar una tarea solamente porque una pantalla se ve bien o un endpoint responde 200: comprobar sus restricciones, errores y efectos sobre el intento.

## 6. Verificación final del recorrido

- [ ] Un miembro con rostro enrolado y habilidad ofrecida puede solicitar la evaluación.
- [ ] Sin consentimiento no se activan las verificaciones ni comienza el examen.
- [ ] Un ambiente que no cumple condiciones obligatorias impide comenzar y ofrece indicaciones para corregirlo.
- [ ] Identidad y prueba de vida se verifican antes del inicio.
- [ ] Todas las habilidades utilizan las tres etapas: teoría, práctica específica y defensa.
- [ ] Teoría y defensa cambian su contenido según la habilidad sin duplicar el flujo.
- [ ] El mismo anticopia supervisa las tres etapas y puede integrarse con programación, guitarra y deportes.
- [ ] Tu práctica de programación está implementada; las prácticas de las otras disciplinas se verifican con sus responsables, sin dar su implementación por terminada.
- [ ] Los incidentes no se duplican y se distinguen de fallas técnicas.
- [ ] La defensa utiliza la evidencia de la práctica correspondiente; en programación, tanto defensa como similitud utilizan la entrega final de código.
- [ ] Un aprobado recibe el resultado y sello correctos.
- [ ] Un no aprobado recibe feedback sin sello.
- [ ] Un caso pendiente de revisión no recibe un dictamen definitivo por accidente.
- [ ] La apelación y su resolución tienen trazabilidad.
- [ ] No se pueden consultar ni modificar intentos ajenos.
- [ ] Finalizar nuevamente no duplica resultados ni certificados.
- [ ] Al terminar se detiene la supervisión y se liberan cámara y micrófono.

## 7. Resumen del flujo

```text
Perfil con rostro registrado + habilidad ofrecida
                         ↓
              Instrucciones y consentimiento
                         ↓
         Comprobar ambiente + identidad + prueba de vida
                         ↓
                  Comenzar evaluación
                         ↓
       ┌────── MISMO ANTICOPIA PARA TODAS ──────┐
       │ 1. Teoría: preguntas de la habilidad   │
       │                  ↓                    │
       │ 2. Práctica específica:                │
       │    código / guitarra / deporte        │
       │                  ↓                    │
       │ 3. Defensa: preguntas sobre la práctica│
       │                                       │
       │ Pestañas + cámara + identidad + eventos│
       └───────────────────────────────────────┘
                         ↓
       Consolidar resultados e incidentes
       (en código, también métricas AST y similitud)
                         ↓
             Resultado o revisión humana
                         ↓
                  Sello, si corresponde
```

**Primera meta concreta:** cualquier miembro con una habilidad ofrecida puede aceptar las condiciones, corregir iluminación o encuadre, verificar su identidad y recién entonces quedar habilitado para rendir. Usar Python como primer escenario de integración, sin acoplar la preparación, teoría, defensa ni anticopia a programación. Después integrar las prácticas de las otras disciplinas con sus responsables.
