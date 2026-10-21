import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.user import User, UserRole

logger = logging.getLogger("skillmatch.seed")

async def ensure_initial_admin(db: AsyncSession) -> None:
    """
    Garantiza la existencia del Administrador inicial del sistema.
    - Se ejecuta automáticamente durante el startup de la aplicación.
    - No utiliza datos ficticios o de prueba: las credenciales provienen
      estrictamente de las variables de entorno (.env): ADMIN_EMAIL, ADMIN_PASSWORD y ADMIN_FULL_NAME.
    - Es 100% idempotente: si el usuario ya existe, no realiza ninguna inserción duplicada.
    """
    email = settings.ADMIN_EMAIL.lower().strip()

    # 1. Verificar si el usuario administrador ya existe
    result = await db.execute(select(User).where(User.email == email))
    existing_user = result.scalar_one_or_none()

    if existing_user:
        # Asegurar que conserve rol ADMIN y esté activo si fue creado previamente
        if existing_user.role != UserRole.ADMIN or not existing_user.is_active:
            existing_user.role = UserRole.ADMIN
            existing_user.is_active = True
            await db.commit()
            logger.info(f"Estado de cuenta para administrador {email} sincronizado.")
        return

    # 2. Crear el único administrador inicial autorizado
    hashed_pwd = get_password_hash(settings.ADMIN_PASSWORD.get_secret_value())
    admin_user = User(
        email=email,
        full_name=settings.ADMIN_FULL_NAME,
        hashed_password=hashed_pwd,
        role=UserRole.ADMIN,
        is_active=True,
        is_locked=False,
        failed_login_attempts=0,
        provider="institutional"
    )

    db.add(admin_user)
    try:
        await db.commit()
        logger.info(f"Administrador inicial provisionado exitosamente desde variables de entorno: {email}")
    except Exception as exc:
        await db.rollback()
        logger.error(f"Error al provisionar el administrador inicial: {exc}")
        raise
