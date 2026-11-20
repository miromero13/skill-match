"""
SkillMatch — CLI para Creación y Sincronización de Super Administradores
========================================================================
Permite crear o restablecer una cuenta administrativa con privilegios totales (rol ADMIN).

Uso:
    python scripts/create_superadmin.py
    python scripts/create_superadmin.py --email admin@skillmatch.com --password Test@123
    python scripts/create_superadmin.py --email superadmin@skillmatch.com --password Admin@123456 --name "Super Admin"
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Agregar raíz del backend al path
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select
from app.core.config import settings
from app.core.security import get_password_hash
from app.db.session import AsyncSessionLocal
from app.models.user import User, UserRole

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("skillmatch.superadmin")


async def create_or_update_superadmin(email: str, password: str, full_name: str) -> None:
    clean_email = email.lower().strip()
    hashed_pwd = get_password_hash(password)

    async with AsyncSessionLocal() as db:
        res = await db.execute(select(User).where(User.email == clean_email))
        user = res.scalar_one_or_none()

        if user:
            logger.info(f"Actualizando usuario existente '{clean_email}' con privilegios de Super Administrador...")
            user.role = UserRole.ADMIN
            user.full_name = full_name
            user.hashed_password = hashed_pwd
            user.is_active = True
            user.is_locked = False
            user.failed_login_attempts = 0
            user.provider = "institutional"
            await db.commit()
            logger.info(f"¡Usuario '{clean_email}' actualizado exitosamente como Super Administrador!")
        else:
            logger.info(f"Creando nuevo Super Administrador '{clean_email}'...")
            new_user = User(
                email=clean_email,
                full_name=full_name,
                hashed_password=hashed_pwd,
                role=UserRole.ADMIN,
                is_active=True,
                is_locked=False,
                failed_login_attempts=0,
                provider="institutional",
            )
            db.add(new_user)
            await db.commit()
            logger.info(f"¡Super Administrador '{clean_email}' creado exitosamente!")

    print("\n" + "=" * 60)
    print("  CREDENCIALES DE ACCESO AL PANEL ADMINISTRATIVO")
    print("=" * 60)
    print(f"  URL del Panel:  https://skillmatch-app.southafricanorth.cloudapp.azure.com/admin/login")
    print(f"  Correo:         {clean_email}")
    print(f"  Contraseña:     {password}")
    print(f"  Rol:            ADMIN")
    print("=" * 60 + "\n")


def main() -> None:
    default_email = settings.ADMIN_EMAIL.lower().strip()
    default_pass = settings.ADMIN_PASSWORD.get_secret_value()
    default_name = settings.ADMIN_FULL_NAME

    parser = argparse.ArgumentParser(description="SkillMatch Super Admin Creator")
    parser.add_argument(
        "--email",
        default=default_email,
        help=f"Correo del super administrador (por defecto: {default_email})",
    )
    parser.add_argument(
        "--password",
        default=default_pass,
        help=f"Contraseña de acceso (por defecto: valor de ADMIN_PASSWORD en .env)",
    )
    parser.add_argument(
        "--name",
        default=default_name,
        help=f"Nombre completo (por defecto: {default_name})",
    )

    args = parser.parse_args()
    asyncio.run(create_or_update_superadmin(args.email, args.password, args.name))


if __name__ == "__main__":
    main()
