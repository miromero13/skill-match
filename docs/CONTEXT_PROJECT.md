# SkillMatch — Documento de Contexto del Proyecto (Master Project Context)

## 1. Información General y Resumen Ejecutivo

- **Nombre del Proyecto:** SkillMatch
- **Modelo:** Plataforma colaborativa web y móvil de intercambio de habilidades (*Skill Swapping*) bajo modelo SaaS.
- **Diferenciador Clave:** Sistema de validación de habilidades asistido por Inteligencia Artificial (modelos especializados para programación, instrumentos musicales y fútbol), supervisión anti-fraude activa y motor de compatibilidad bidireccional (*matching* recíproco).

---

## 2. Descripción del Problema y Justificación

### 2.1 Problemática
1. **Barrera económica de formación:** El acceso a capacitación especializada suele implicar altos costos financieros.
2. **Falta de confianza en plataformas de intercambio:** En entornos digitales abiertos es difícil verificar si una persona realmente domina la habilidad y el nivel que declara.
3. **Fricción en la búsqueda y emparejamiento manual:** Encontrar manualmente a alguien que enseñe lo que uno busca y a la vez quiera aprender lo que uno domina genera frustración y pérdida de tiempo.

### 2.2 Propuesta de Valor
SkillMatch formaliza el aprendizaje entre pares (*peer-to-peer learning*) eliminando la intermediación monetaria directa e introduciendo **confianza algorítmica y verificada**. Mediante evaluaciones teóricas y prácticas evaluadas por modelos de Machine Learning y visión por computadora, el sistema otorga sellos y niveles verificados para garantizar intercambios legítimos y efectivos.

---

## 3. Objetivos

### 3.1 Objetivo General
Desarrollar una plataforma web y móvil para el intercambio de habilidades entre usuarios, incorporando mecanismos de coincidencia bidireccional y modelos de inteligencia artificial que permitan validar determinadas habilidades y aumentar la confianza durante el proceso de intercambio de conocimientos.

### 3.2 Objetivos Específicos
1. Implementar el sistema de registro, autenticación segura y gestión de perfiles de usuario.
2. Permitir el registro catalogado de habilidades ofrecidas (a enseñar) y demandadas (a aprender).
3. Construir un motor de coincidencias (*matching engine*) que correlacione usuarios según habilidades, modalidades, disponibilidad y niveles.
4. Desarrollar el módulo de evaluación teórica y práctica asistida por IA para validación de competencias.
5. Entrenar y desplegar modelos especializados de Machine Learning / Visión / Audio para las tres áreas iniciales: **Programación**, **Instrumentos Musicales** y **Fútbol**.
6. Generar métricas objetivas y niveles verificados con sellos de autenticidad para los perfiles.
7. Diseñar interfaces web y móvil responsivas e intuitivas con monitoreo de sesiones y prevención de fraude.

---

## 4. Alcance Funcional por Módulos

### Módulo 1: Gestión de Usuarios y Accesos (RF-US)
- Registro y autenticación de usuarios (JWT).
- Gestión y edición de perfil personal y profesional.
- Control de acceso basado en roles (RBAC: Usuario, Administrador, Especialista/Evaluador).
- Configuración de disponibilidad horaria y modalidad de intercambio (presencial, virtual o híbrida).

### Módulo 2: Gestión de Habilidades (RF-SK)
- Catálogo maestro de habilidades agrupadas por categorías.
- Registro de habilidades ofrecidas (con nivel auto-declarado inicial).
- Registro de habilidades deseadas/solicitadas.
- Transición de estado: habilidad declarada vs. habilidad verificada con nivel certificado.

### Módulo 3: Evaluación y Validación de Habilidades (RF-EV)
- **Evaluaciones Teóricas:** Cuestionarios dinámicos y aleatorios sobre fundamentos conceptuales.
- **Evaluaciones Prácticas por Dominio:**
  - *Programación:* Resolución de retos de código y explicación de la solución.
  - *Instrumentos Musicales:* Ejecución práctica frente a cámara y micrófono analizada por audio/visión.
  - *Fútbol / Deportes:* Ejecución de pruebas físicas y técnicas frente a la cámara (visión artificial).
- Cálculo automatizado de puntuación y asignación de nivel alcanzado.
- Otorgamiento de **Sello de Habilidad Verificada**.

### Módulo 4: Búsqueda, Matching e Intercambio (RF-MA)
- Búsqueda parametrizada con filtros por habilidad, nivel verificado, modalidad y ubicación.
- Motor de compatibilidad bidireccional (*reciprocal matching*).
- Cálculo de porcentaje de compatibilidad basado en intereses mutuos, nivel, modalidad y agenda.
- Tarjeta de coincidencia (*match card*) con resumen claro de intercambio propuesto.

### Módulo 5: Supervisión y Prevención de Fraude (RF-SU)
- Banco de preguntas y desafíos con rotación aleatoria y límites de tiempo estrictos.
- Control de foco de ventana y detección de cambio de pestaña o aplicación.
- Cámara y micrófono activos durante la evaluación.
- Detección de múltiples rostros y presencia continua del usuario (*Computer Vision*).
- Detección de voces accesorias / asistentes externos (*Audio Processing*).
- Prueba de vida (*liveness detection*) para mitigar suplantación con fotos o videos pregrabados.
- Verificación previa del entorno (iluminación, hardware, conexión y visibilidad).
- Restricción de portapapeles (copiar/pegar) en entornos controlados de código.

### Módulo 6: Inteligencia Artificial y Gestión de Datasets (RF-IA)
- Administración y curaduría de datasets de entrenamiento para cada vertical.
- Modelo especializado de Fútbol (análisis de movimiento corporal y postura).
- Modelo especializado de Instrumentos Musicales (análisis espectral de audio y digitación/postura).
- Modelo especializado de Programación (análisis estático, pruebas funcionales y razonamiento del código).
- Pipeline de reentrenamiento, versionado de modelos y ajuste de umbrales métricos.

### Módulo 7: Sesiones de Intercambio (RF-SE)
- Coordinación y agendamiento de encuentros (fechas, horarios, enlaces virtuales o puntos de encuentro).
- Registro de ciclo de vida de la sesión (programada, en curso, cumplida, cancelada o reprogramada).

### Módulo 8: Reputación y Confianza (RF-RE)
- Sistema recíproco de valoraciones y reseñas post-intercambio.
- Índice de credibilidad del usuario (tasa de cumplimiento, puntualidad, calidad pedagógica).
- Historial público de intercambios exitosos.

### Módulo 9: Notificaciones en Tiempo Real (RF-NT)
- Comunicación bidireccional vía WebSockets (FastAPI).
- Notificaciones push y en aplicación sobre nuevos matches, mensajes, confirmaciones y estados de evaluación.

---

## 5. Elementos del SIBC (Sistema de Información Basado en Computadoras)

### 5.1 Hardware
- **Servidores de Aplicación:** VPS para backend, servicios auxiliares y bases de datos.
- **Servidores GPU Dedicados:** Instancias con aceleración gráfica para inferencia y entrenamiento de PyTorch (análisis de video, imagen y audio).
- **Dispositivos Clientes:** Laptops/PCs y smartphones/tablets equipados obligatoriamente con cámara web y micrófono para las etapas de evaluación.

### 5.2 Software y Stack Tecnológico
- **Backend:** Python + FastAPI (asíncrono, OpenAPI nativo, alto rendimiento).
- **Inteligencia Artificial y ML:** PyTorch, OpenCV, bibliotecas especializadas de procesamiento de señales de audio y NLP.
- **Frontend Web:** React.js con TypeScript (arquitectura modular basada en componentes).
- **Frontend Móvil:** Capacitor (empaquetado multiplataforma sobre React/TypeScript con acceso a APIs nativas de cámara y micrófono).
- **Base de Datos Relacional:** PostgreSQL (integridad referencial, transacciones ACID y alta concurrencia).
- **Almacenamiento de Objetos:** MinIO autogestionado en VPS para datasets, videos, audios y evidencias.
- **Tiempo Real:** WebSockets integrados en FastAPI.
- **Seguridad:** JWT (JSON Web Tokens) con control de acceso granular por roles (RBAC).

### 5.3 Datos
- Datos de usuarios, credenciales hasheadas y perfiles.
- Catálogo de habilidades y taxonomía.
- Datasets específicos por vertical (deporte, música, código).
- Grabaciones de video, pistas de audio y fragmentos de código enviados en evaluaciones.
- Logs de supervisión (incidencias de foco, rostros, eventos biométricos).
- Métricas, scores de compatibilidad y registros de sesiones de intercambio.

### 5.4 Procedimientos
1. Registro y configuración de perfil.
2. Declaración de oferta y demanda de habilidades.
3. Verificación de entorno de hardware previo a pruebas.
4. Ejecución supervisada de evaluaciones teóricas/prácticas.
5. Inferencia por IA, cálculo de métricas y certificación de nivel.
6. Matching recíproco y presentación de candidatos compatibles.
7. Agendamiento, ejecución y calificación de sesiones de intercambio.
8. Gestión, auditoría y reentrenamiento de datasets.

### 5.5 Personas y Roles
- **Usuarios Registrados:** Aprendices y enseñantes en el ecosistema.
- **Administradores del Sistema:** Gestores del catálogo, parámetros globales y monitoreo de plataforma.
- **Especialistas en IA y Evaluadores:** Responsables de la calidad de los datasets, auditoría de modelos y resolución de casos de fraude/borde.

---

## 6. Arquitectura y Modelado (Modelo C4 & Enterprise Architect)

El diseño del sistema se estructura mediante el **Modelo C4** gestionado centralizadamente con **Enterprise Architect (EA)**:
- **Nivel 1 (Contexto):** Interacción de usuarios y administradores con SkillMatch y sistemas externos de notificación/almacenamiento.
- **Nivel 2 (Contenedores):** Separación desacoplada entre SPA Web (React), App Móvil (Capacitor), API Gateway / Core (FastAPI), Inferencia IA (PyTorch Services), Base de Datos (PostgreSQL) y Almacenamiento (MinIO).
- **Nivel 3 (Componentes):** Controladores de autenticación, gestor de catálogo, motor de matching, supervisor anti-fraude y evaluadores de IA por disciplina.
- **Nivel 4 (Código):** Diagramas de clases e interfaces específicas para los motores de scoring y evaluación.

---

## 7. Infraestructura y Despliegue (IaaS)

- **Plataforma de Despliegue:** VPS autogestionado con orquestación vía **Coolify**.
- **Gestión de Código y CI/CD:** Repositorio en GitHub con branching strategy estructurado, Pull Requests obligatorios y soporte Git LFS para artefactos de modelos.
- **Trazabilidad de Gestión:** Integración de GitHub con **Jira Software** bajo metodología ágil **Scrum**.

---

## 8. Paquetes de Casos de Uso y Especificación Detallada

El desglose exhaustivo de los 146 Requisitos Funcionales, prioridades (A/M/B), elementos innovadores (★), restricciones de IA propia y planificación por sprints se encuentra formalizado en el documento de ingeniería de requisitos:
👉 **[`docs/FUNCTIONAL_REQUIREMENTS.md`](./FUNCTIONAL_REQUIREMENTS.md)**

### Estructura de Paquetes (Backlog Maestro)
- **P1:** Gestión de Usuarios y Accesos (`RF-USR-01` a `RF-USR-17`)
- **P2:** Gestión de Habilidades y Catálogo (`RF-HAB-01` a `RF-HAB-13`)
- **P3:** Evaluación y Validación de Habilidades con IA (`RF-EVA-01` a `RF-EVA-24`)
- **P4:** Búsqueda, Matching e Intercambio Bidireccional (`RF-MAT-01` a `RF-MAT-16`)
- **P5:** Supervisión y Prevención de Fraude (`RF-FRA-01` a `RF-FRA-20`)
- **P6:** Inteligencia Artificial, Datasets y Retos (`RF-IA-01` a `RF-IA-23`)
- **P7:** Coordinación y Seguimiento de Intercambios (`RF-SES-01` a `RF-SES-15`)
- **P8:** Reputación, Analítica y Métricas de Rendimiento (`RF-REP-01` a `RF-REP-09` y `RF-NOT-01` a `RF-NOT-09`)

