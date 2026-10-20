from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.middlewares import setup_middlewares
from app.core.exceptions import (
    SkillMatchException,
    skillmatch_exception_handler,
    http_exception_handler,
    validation_exception_handler,
    unhandled_exception_handler,
)
from app.api.health import health_router

logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("skillmatch.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida de la aplicación FastAPI (startup y shutdown)."""
    logger.info(f"Iniciando {settings.PROJECT_NAME} v{settings.VERSION} en entorno '{settings.ENVIRONMENT}'...")
    yield
    logger.info("Cerrando conexiones y apagando servicios de SkillMatch API...")


def create_application() -> FastAPI:
    """Fábrica para instanciar y configurar la aplicación FastAPI."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description=settings.DESCRIPTION,
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # 1. Configuración de Middlewares (CORS, GZip, Security Headers)
    setup_middlewares(app)

    # 2. Registro de Manejadores Centralizados de Excepciones (APIResponse Envelope)
    app.add_exception_handler(SkillMatchException, skillmatch_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # 3. Montaje de Routers Modulares
    app.include_router(health_router, prefix="/api")

    return app

app = create_application()
