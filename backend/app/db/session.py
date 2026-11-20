import logging
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from app.core.config import settings

logger = logging.getLogger("skillmatch.db")

# Creación del engine asíncrono optimizado con connection pooling
async_engine = create_async_engine(
    settings.async_database_url,
    echo=False,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_pre_ping=True,
    future=True,
)

# Fábrica de sesiones asíncronas
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

# Background work detached from the request (post-commit native push dispatch). NullPool:
# every session opens and closes its own connection on the current event loop, so no
# pooled asyncpg connection can outlive the loop that created it (Celery asyncio.run,
# per-test loops) or compete with the request pool.
background_engine = create_async_engine(settings.async_database_url, echo=False, poolclass=NullPool)

BackgroundSessionLocal = async_sessionmaker(
    bind=background_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Inyector de dependencias FastAPI para obtener una sesión de base de datos asíncrona.
    Garantiza commit automático o rollback ante excepciones.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as exc:
            await session.rollback()
            logger.error(f"Error en transacción de BD: {exc}")
            raise
        finally:
            await session.close()
