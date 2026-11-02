import logging
import uuid
from typing import Tuple, List
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import status

from app.core.exceptions import SkillMatchException
from app.core.security import get_password_hash
from app.models.user import User, UserRole
from app.schemas.admin import AdminCreateRequest, AdminStatusUpdateRequest

logger = logging.getLogger("skillmatch.admin_service")

class AdminService:
    """Servicio de dominio para la gestión y gobernanza de administradores (RF-USR-10, RF-USR-15)."""

    @staticmethod
    async def list_administrators(
        db: AsyncSession
    ) -> Tuple[List[User], int]:
        """
        Retorna la lista de todas las cuentas con rol ADMIN y el conteo total.
        """
        # Conteo total
        count_stmt = select(func.count(User.id)).where(User.role == UserRole.ADMIN)
        count_res = await db.execute(count_stmt)
        total_count = count_res.scalar() or 0

        # Listado ordenado por fecha de creación descendente
        stmt = (
            select(User)
            .where(User.role == UserRole.ADMIN)
            .order_by(User.created_at.desc())
        )
        result = await db.execute(stmt)
        admins = list(result.scalars().all())

        return admins, total_count

    @staticmethod
    async def create_administrator(
        db: AsyncSession,
        request: AdminCreateRequest,
        current_admin: User
    ) -> User:
        """
        Da de alta una nueva cuenta administrativa asegurando unicidad de correo
        y contraseña hasheada con bcrypt.
        """
        clean_email = request.email.strip().lower()

        # Verificar unicidad de correo
        existing_stmt = select(User).where(User.email == clean_email)
        existing_res = await db.execute(existing_stmt)
        if existing_res.scalar_one_or_none():
            logger.warning(
                f"Intento de alta de administrador con correo ya existente: {clean_email}"
            )
            raise SkillMatchException(
                statuscode=status.HTTP_400_BAD_REQUEST,
                message="El correo electrónico ya se encuentra registrado en la plataforma."
            )

        hashed = get_password_hash(request.password)

        new_admin = User(
            id=uuid.uuid4(),
            email=clean_email,
            full_name=request.full_name.strip(),
            hashed_password=hashed,
            role=UserRole.ADMIN,
            is_active=True,
            is_locked=False,
            failed_login_attempts=0,
            provider="institutional"
        )

        db.add(new_admin)
        await db.commit()
        await db.refresh(new_admin)

        logger.info(
            f"[AUDITORÍA RF-USR-10] Nuevo administrador '{new_admin.email}' creado exitosamente "
            f"por el administrador '{current_admin.email}' (ID: {current_admin.id})."
        )

        return new_admin

    @staticmethod
    async def update_administrator_status(
        db: AsyncSession,
        admin_id: uuid.UUID,
        request: AdminStatusUpdateRequest,
        current_admin: User
    ) -> User:
        """
        Suspende o reactiva un administrador con registro de auditoría (RF-USR-15).
        Impide la auto-suspensión de la cuenta propia del administrador en sesión.
        """
        # Prevención de auto-suspensión
        if admin_id == current_admin.id and not request.is_active:
            logger.warning(
                f"El administrador '{current_admin.email}' intentó suspender su propia cuenta."
            )
            raise SkillMatchException(
                statuscode=status.HTTP_400_BAD_REQUEST,
                message="No podés suspender tu propia cuenta administrativa activa."
            )

        # Buscar administrador objetivo
        stmt = select(User).where(User.id == admin_id)
        result = await db.execute(stmt)
        target_admin = result.scalar_one_or_none()

        if not target_admin or target_admin.role != UserRole.ADMIN:
            raise SkillMatchException(
                statuscode=status.HTTP_404_NOT_FOUND,
                message="Administrador no encontrado."
            )

        # Actualizar estado
        target_admin.is_active = request.is_active
        if request.is_active:
            # Reactivación limpia también bloqueos por intentos fallidos
            target_admin.is_locked = False
            target_admin.failed_login_attempts = 0
            target_admin.locked_until = None

        await db.commit()
        await db.refresh(target_admin)

        status_action = "REACTIVADA" if request.is_active else "SUSPENDIDA"
        logger.info(
            f"[AUDITORÍA RF-USR-15] Cuenta administrativa '{target_admin.email}' {status_action} "
            f"por '{current_admin.email}'. Motivo: '{request.reason or 'Sin motivo especificado'}'."
        )

        return target_admin
