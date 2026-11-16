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
