import logging
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.db.session import get_db
from app.schemas.response import APIResponse
from app.schemas.health import HealthData
from app.core.config import settings

logger = logging.getLogger("skillmatch.api.health")

router = APIRouter(prefix="/health", tags=["Health & Status"])

@router.get(
    "",
    response_model=APIResponse[HealthData],
    status_code=status.HTTP_200_OK,
    summary="Verificación de salud del sistema",
    description="Evalúa el estado del servidor FastAPI y la conectividad activa con PostgreSQL.",
)
async def check_health(db: AsyncSession = Depends(get_db)) -> APIResponse[HealthData]:
    db_status = "disconnected"
    try:
        # Ejecución de verificación ligera en PostgreSQL
        result = await db.execute(text("SELECT 1"))
        if result.scalar() == 1:
            db_status = "connected"
    except Exception as exc:
        logger.warning(f"Error verificando conectividad a base de datos en /health: {exc}")
        db_status = "disconnected"

    overall_status = "healthy" if db_status == "connected" else "degraded"

    data = HealthData(
        status=overall_status,
        environment=settings.ENVIRONMENT,
        version=settings.VERSION,
        database=db_status,
        services={
            "api": "operational",
            "database_engine": "asyncpg_sqlalchemy2",
        },
    )

    message = (
        "Sistema operativo y base de datos conectada exitosamente"
        if db_status == "connected"
        else "Servidor activo pero con degradación en la conexión a la base de datos"
    )

    return APIResponse[HealthData](
        statuscode=status.HTTP_200_OK,
        message=message,
        data=data,
        count=None,
    )
