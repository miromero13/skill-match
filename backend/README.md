# SkillMatch — Backend API

Backend asíncrono para la plataforma de intercambio colaborativo de habilidades **SkillMatch**, construido con **FastAPI**, **SQLAlchemy 2.0 (asyncpg)**, **PostgreSQL** y **Alembic**.

---

## 1. Arquitectura y Tecnologías
- **Framework:** FastAPI con arquitectura modular por dominio.
- **ORM & Persistencia:** SQLAlchemy 2.0 con driver asíncrono `asyncpg`.
- **Migraciones:** Alembic configurado para ejecución asíncrona.
- **Contrato de Respuesta:** Sobre unificado y estándar `APIResponse[T]` (`statuscode`, `message`, `data`, `count`).
- **Seguridad:** Middlewares de CORS, compresión GZip, cabeceras preventivas y tokens JWT con claim dinámico de rol (`MEMBER` o `ADMIN`).
- **Documentación Viva:** Swagger UI interactivo en `/docs` y ReDoc en `/redoc`.

---

## 2. Requisitos Previos
- Python 3.12+ (recomendado Python 3.13)
- Gestor de paquetes rápido `uv` (o `pip`)
- Docker y Docker Compose (para base de datos PostgreSQL y despliegue contenedorizado)

---

## 3. Puesta en Marcha

### Opción A: Ejecución con Docker Compose (Recomendado para desarrollo completo)
Para levantar la base de datos PostgreSQL persistente y la API FastAPI contenedorizada:
```bash
# Desde la raíz del repositorio:
docker compose up -d --build

# Ver logs de la API:
docker compose logs -f api
```
- La API estará accesible en: `http://localhost:8000`
- Documentación Swagger UI: `http://localhost:8000/docs`
- Verificación de salud: `http://localhost:8000/api/health`

---

### Opción B: Ejecución Local en Entorno Virtual

1. **Configurar el entorno virtual con `uv`:**
   ```bash
   cd backend
   uv venv .venv --python python3.13
   source .venv/bin/activate
   uv pip install -e ".[dev]"
   ```

2. **Configurar variables de entorno:**
   Copia la plantilla `env.template` al archivo de configuración de entorno:
   ```bash
   cp env.template .env
   ```

3. **Levantar PostgreSQL con Docker:**
   ```bash
   # En la raíz del proyecto:
   docker compose up -d postgres
   ```

4. **Ejecutar migraciones de base de datos con Alembic:**
   ```bash
   cd backend
   alembic upgrade head
   ```

5. **Iniciar el servidor de desarrollo:**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

---

## 4. Ejecución de Pruebas Automatizadas (Pytest)
Para correr la suite de pruebas unitarias y de integración:
```bash
cd backend
pytest -v
```

---

## 5. Esquema del Sobre de Respuesta (APIResponse)
Todas las rutas responden estrictamente bajo este formato JSON:
```json
{
  "statuscode": 200,
  "message": "Operación completada exitosamente",
  "data": {
    "status": "healthy",
    "environment": "development",
    "version": "0.1.0",
    "database": "connected"
  },
  "count": null
}
```
En caso de error (400, 404, 422, 500), el middleware captura la excepción y la traduce automáticamente al sobre estándar con su respectivo `statuscode` y `message` descriptivo.
