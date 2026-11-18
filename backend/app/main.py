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
from app.api.admin.auth import admin_auth_router
from app.api.admin.router import router as admin_management_router
from app.api.admin.catalog import router as admin_catalog_router
from app.api.admin.theory_questions import router as theory_question_router
from app.api.auth import auth_router
from app.api.evaluations import router as evaluation_preflight_router
from app.api.theory_exam import router as theory_exam_router
from app.api.browser_supervision import router as browser_supervision_router
from app.api.skills.router import router as public_skills_router
from app.api.users.learning_skills import router as user_learning_skills_router
from app.db.session import AsyncSessionLocal
from app.db.seed import ensure_initial_admin
from app.api.users.teaching_skills import router as teaching_skills_router
from app.schemas.response import APIResponse
from app.api.users.skill_evidences import router as skill_evidences_router
from app.api.ai.datasets import router as ai_dataset_router
from app.football.api import router as football_router
from app.api.notifications.router import router as notifications_router
from app.api.notifications.websocket import router as notification_websocket_router
from app.services.notification_connection_manager import notification_connection_manager
from app.api.users.notification_preferences import router as notification_preferences_router
from app.api.users.profile import router as user_profile_router
from app.api.users.availability import router as user_availability_router
from app.api.matches.router import router as matches_router
from app.api.search import search_router
from app.api.users.moderation import router as user_moderation_router

logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("skillmatch.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida de la aplicación FastAPI (startup y shutdown)."""
    logger.info(f"Iniciando {settings.PROJECT_NAME} v{settings.VERSION} en entorno '{settings.ENVIRONMENT}'...")
    
    # Provisionamiento seguro del Administrador Inicial desde variables de entorno (.env)
    try:
        async with AsyncSessionLocal() as db:
            await ensure_initial_admin(db)
    except Exception as exc:
        logger.error(f"Fallo crítico durante el seed del administrador inicial: {exc}")

    yield
    await notification_connection_manager.close_all()
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
        responses={
            422: {
                "model": APIResponse[None],
                "description": "Datos inválidos: message descriptivo, data null y sin count",
            },
        },
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
    app.include_router(admin_auth_router, prefix="/api")
    app.include_router(admin_management_router, prefix="/api")
    app.include_router(admin_catalog_router, prefix="/api")
    app.include_router(theory_question_router, prefix="/api")
    app.include_router(auth_router, prefix="/api")
    app.include_router(evaluation_preflight_router, prefix="/api")
    app.include_router(theory_exam_router, prefix="/api")
    app.include_router(browser_supervision_router, prefix="/api")
    app.include_router(public_skills_router, prefix="/api")
    app.include_router(user_learning_skills_router, prefix="/api")
    app.include_router(teaching_skills_router, prefix="/api")
    app.include_router(skill_evidences_router, prefix="/api")
    app.include_router(ai_dataset_router, prefix="/api")
    app.include_router(football_router, prefix="/api/football")
    app.include_router(football_router, prefix="/api/v1/football")
    app.include_router(notifications_router, prefix="/api")
    app.include_router(notification_websocket_router)
    app.include_router(notification_preferences_router, prefix="/api")
    app.include_router(user_profile_router, prefix="/api")
    app.include_router(user_availability_router, prefix="/api")
    app.include_router(matches_router, prefix="/api")
    app.include_router(search_router, prefix="/api")
    app.include_router(user_moderation_router, prefix="/api")

    return app

app = create_application()
