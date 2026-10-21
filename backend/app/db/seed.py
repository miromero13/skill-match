"""
Script de seed para crear el usuario Administrador inicial de SkillMatch.
Permite autenticarse inmediatamente en /admin/login con las credenciales de desarrollo.
"""
import asyncio
import logging
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.core.security import get_password_hash
from app.models.user import User, UserRole

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("skillmatch.seed")

INITIAL_ADMIN_EMAIL = "admin.gonzalo@skillmatch.io"
INITIAL_ADMIN_PASSWORD = "SuperSecretAdminPassword123!"
INITIAL_ADMIN_NAME = "Gonzalo Administrador Inicial"

async def seed_initial_admin() -> None:
    async with AsyncSessionLocal() as db:
        # Verificar si ya existe
        result = await db.execute(select(User).where(User.email == INITIAL_ADMIN_EMAIL))
        existing_admin = result.scalar_one_or_none()

        if existing_admin:
            logger.info(f"El administrador inicial ya existe en la base de datos: {INITIAL_ADMIN_EMAIL}")
            return

        admin_user = User(
            email=INITIAL_ADMIN_EMAIL,
            full_name=INITIAL_ADMIN_NAME,
            hashed_password=get_password_hash(INITIAL_ADMIN_PASSWORD),
            role=UserRole.ADMIN,
            is_active=True,
            is_locked=False,
            failed_login_attempts=0,
            provider="institutional"
        )
        db.add(admin_user)
        await db.commit()
        logger.info(f"Administrador inicial creado exitosamente: {INITIAL_ADMIN_EMAIL}")
        logger.info(f"Credenciales de prueba: Email='{INITIAL_ADMIN_EMAIL}' | Password='{INITIAL_ADMIN_PASSWORD}'")

if __name__ == "__main__":
    asyncio.run(seed_initial_admin())
