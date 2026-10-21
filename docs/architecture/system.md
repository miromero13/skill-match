# SkillMatch — Arquitectura Integral del Sistema (System Architecture)

*Documento de referencia técnica para el ecosistema global de SkillMatch.*

---

## 1. Visión General del Sistema y Objetivos

**SkillMatch** es una plataforma distribuida diseñada para facilitar el intercambio recíproco de conocimientos entre pares (*peer-to-peer learning*) sin intermediación monetaria forzosa, sustituyendo la desconfianza de internet por **validación algorítmica y biométrica asistida por IA propia**.

### Objetivos Arquitectónicos
1. **Desacoplamiento Estricto:** Frontend desacoplado del Backend vía APIs RESTful asíncronas y WebSockets.
2. **Soberanía de Datos e Inferencia Local:** Ningún dato personal, biométrico ni solución técnica se envía a proveedores cerrados de IA (OpenAI, Anthropic, Gemini).
3. **Resiliencia y Concurrencia:** Alta capacidad de manejo de conexiones en tiempo real para sesiones de estudio, telemetría de exámenes y matching.
4. **Seguridad por Diseño (Security by Design):** Ofuscación de rutas administrativas mediante respuestas 404, sandbox Docker rootless para ejecución de código y tokens JWT efímeros.

---

## 2. Diagrama de Contenedores del Sistema (C4 - Nivel 2)

```
+-----------------------------------------------------------------------------------+
|                                  DISPOSITIVOS CLIENTE                             |
|                                                                                   |
|  +-------------------------------------+   +-----------------------------------+  |
|  |     Navegador Web (Desktop/Tablet)  |   |     Aplicación Móvil (Android/iOS)|  |
|  |     React 19 + TypeScript + Zustand |   |     Capacitor + React + Zustand   |  |
|  +------------------+------------------+   +-----------------+-----------------+  |
+---------------------|----------------------------------------|--------------------+
                      | HTTPS / WSS (REST & WebSockets)        |
                      v                                        v
+-----------------------------------------------------------------------------------+
|                           INFRAESTRUCTURA BACKEND (VPS / Docker)                  |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  |                     Reverse Proxy & SSL Termination (Traefik/Nginx)         |  |
|  +---------------------------------------+-------------------------------------+  |
|                                          |                                        |
|                                          v                                        |
|  +-----------------------------------------------------------------------------+  |
|  |                        SkillMatch Backend API (FastAPI)                     |  |
|  |  - Routers Modulares (/api/auth, /api/users, /api/evaluations, etc.)        |  |
|  |  - Exception Handlers (Formato APIResponse)                                 |  |
|  |  - Motor de Matching Bilateral & Cadenas Triangulares (Grafos)               |  |
|  |  - WebSocket Manager para notificaciones y telemetría de exámenes          |  |
|  +---------------------+-------------------+-------------------+---------------+  |
|                        |                   |                   |                  |
|        SQLAlchemy Async|                   | S3 / Multipart    | Docker Socket    |
|        (asyncpg)       |                   | (minio-py)        | (API Interna)    |
|                        v                   v                   v                  |
|  +---------------------------+ +---------------------+ +-----------------------+  |
|  |    PostgreSQL 16          | |  MinIO Object Store | | Docker Sandbox Runner |  |
|  |  - Usuarios & Perfiles    | |  - Grabaciones WAV  | |  - Contenedor aislado |  |
|  |  - Catálogo Habilidades   | |  - Videos MP4 retos | |  - Límites CPU / RAM  |  |
|  |  - Sesiones & Billetera   | |  - Datasets IA      | |  - Pytest Execution   |  |
|  |  - Auditoría & Telemetría | |  - PDF Pasaportes   | |  - AST Validation     |  |
|  +---------------------------+ +---------------------+ +-----------------------+  |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  |                    Workers de Inferencia Local (PyTorch / librosa)          |  |
|  |  - Evaluador Acústico (Mel Spectrograms, Pitch, BPM)                        |  |
|  |  - Evaluador Deportivo (OpenCV, Pose Tracking de Balón)                     |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

---

## 3. Modelo de Comunicación y Protocolos

| Flujo | Protocolo | Formato Payload | Propósito |
|---|---|---|---|
| **API REST General** | HTTPS | JSON (`APIResponse`) | Autenticación, perfiles, catálogo, pasaportes, billetera. |
| **Tiempo Real & Alertas** | WSS (WebSockets) | JSON estructurado | Notificaciones push, eventos de examen y telemetría anti-fraude. |
| **Ingesta de Evidencias** | HTTPS Multipart | Binario (WAV, MP4, PNG) | Subida de grabaciones de pruebas teóricas y datasets para reentrenamiento. |
| **Sandbox de Código** | IPC / Docker API | stdin / stdout JSON | Ejecución aislada de código de usuario y retorno de reportes de test. |

---

## 4. Estrategia Global de Seguridad y Protección de Datos

1. **Gobernanza de Roles (RBAC):**
   - Dos roles exclusivos: `MEMBER` y `ADMIN`.
   - Autenticación diferenciada: miembros nunca tienen contraseñas en la base de datos (se previenen filtraciones y ataques de fuerza bruta).
2. **Defensa en Profundidad contra Ataques Web:**
   - CORS estricto configurable vía `.env`.
   - Compresión GZip para respuestas mayores a 1000 bytes.
   - Headers HTTP de seguridad (`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Strict-Transport-Security`).
3. **Ofuscación Activa (404 Not Found):**
   - Para cualquier actor que no presente el claim `"role": "ADMIN"`, los endpoints y pantallas `/admin` son indistinguibles de una ruta inexistente.
4. **Protección Criptográfica del Pasaporte QR:**
   - La URL pública asociada al QR contiene una firma digital institucional verificable contra la clave pública del servidor, impidiendo la falsificación de credenciales de habilidades.
