import logging
from typing import Optional
from uuid import UUID
from fastapi import Depends, Header, status
from jose import jwt, JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import SkillMatchException
from app.db.session import get_db
from app.models.user import User, UserRole

logger = logging.getLogger("skillmatch.deps")

async def get_current_user_from_token(
    authorization: Optional[str] = Header(None, description="Bearer <token>"),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Extrae, valida y decodifica el token JWT de acceso.
    Retorna la entidad User persistida en base de datos.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise SkillMatchException(
            statuscode=status.HTTP_401_UNAUTHORIZED,
            message="Encabezado de autorización ausente o con formato inválido (se requiere 'Bearer <token>')."
        )

    token = authorization.split(" ")[1]

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY.get_secret_value(),
            algorithms=[settings.ALGORITHM]
        )
        user_id_str: Optional[str] = payload.get("sub")
        token_type: Optional[str] = payload.get("type")

        if not user_id_str or token_type != "access":
            raise SkillMatchException(
                statuscode=status.HTTP_401_UNAUTHORIZED,
                message="Token de acceso inválido o expirado."
            )

        user_id = UUID(user_id_str)
    except (JWTError, ValueError) as exc:
        logger.warning(f"Error decodificando token JWT: {exc}")
        raise SkillMatchException(
            statuscode=status.HTTP_401_UNAUTHORIZED,
            message="Firma del token inválida o expirada. Por favor autentíquese nuevamente."
        )

    # Buscar usuario en base de datos
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise SkillMatchException(
            statuscode=status.HTTP_401_UNAUTHORIZED,
            message="El usuario autenticado ya no existe en el sistema."
        )

    if not user.is_active:
        raise SkillMatchException(
            statuscode=status.HTTP_403_FORBIDDEN,
            message="La cuenta de usuario se encuentra suspendida o inactiva."
        )

    if user.is_locked:
        raise SkillMatchException(
            statuscode=status.HTTP_423_LOCKED,
            message="La cuenta de usuario se encuentra bloqueada por seguridad."
        )

    return user

async def require_admin_role(
    current_user: User = Depends(get_current_user_from_token)
) -> User:
    """
    Guardia de autorización estricta para rol ADMIN.
    POLÍTICA DE SEGURIDAD POR OFUSCACIÓN:
    Si un usuario con rol distinto a ADMIN (ej. MEMBER) intenta acceder a un recurso administrativo,
    el sistema NO responde con 403 Forbidden, sino con 404 Not Found ('Recurso no encontrado'),
    impidiendo que atacantes descubran la existencia o topología de las rutas administrativas.
    """
    if current_user.role != UserRole.ADMIN:
        logger.warning(
            f"Acceso denegado a recurso administrativo por usuario no-admin {current_user.email} (rol {current_user.role}). "
            f"Ofuscando con 404 Not Found."
        )
        raise SkillMatchException(
            statuscode=status.HTTP_404_NOT_FOUND,
            message="Recurso no encontrado"
        )

    return current_user
