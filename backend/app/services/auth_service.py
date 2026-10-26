import logging
from typing import Optional
from uuid import UUID
from fastapi import status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import SkillMatchException
from app.core.security import (
    decode_jwt_payload,
    create_access_token,
    create_refresh_token,
    revoke_token,
)
from app.models.user import User
from app.schemas.auth import TokenRefreshResponse, UserMeResponse

logger = logging.getLogger("skillmatch.services.auth")

class AuthService:
    """
    Servicio de dominio para el ciclo de vida de sesiones JWT unificadas (HU-09).
    Soporta rotación de Refresh Tokens, revocación y consulta de identidad.
    """

    @staticmethod
    async def refresh_tokens(
        db: AsyncSession,
        refresh_token_str: str
    ) -> TokenRefreshResponse:
        """
        Valida el Refresh Token JWT, revoca el token anterior para evitar reuso (Rotation)
        y emite un nuevo par de Access Token y Refresh Token preservando el claim de rol.
        """
        if not refresh_token_str or not refresh_token_str.strip():
            raise SkillMatchException(
                statuscode=status.HTTP_400_BAD_REQUEST,
                message="El Refresh Token es obligatorio para la renovación de sesión."
            )

        clean_token = refresh_token_str.strip()

        try:
            payload = decode_jwt_payload(clean_token)
            user_id_str: Optional[str] = payload.get("sub")
            token_type: Optional[str] = payload.get("type")

            if not user_id_str or token_type != "refresh":
                raise SkillMatchException(
                    statuscode=status.HTTP_401_UNAUTHORIZED,
                    message="El token provisto no es un Refresh Token válido o ha expirado."
                )

            user_id = UUID(user_id_str)
        except SkillMatchException:
            raise
        except (JWTError, ValueError) as exc:
            logger.warning(f"Intento de refresh con token inválido o corrupto: {exc}")
            raise SkillMatchException(
                statuscode=status.HTTP_401_UNAUTHORIZED,
                message="Refresh Token inválido, expirado o revocado. Por favor inicie sesión nuevamente."
            )

        # Buscar usuario en la base de datos
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            raise SkillMatchException(
                statuscode=status.HTTP_401_UNAUTHORIZED,
                message="El usuario asociado a la sesión ya no existe en el sistema."
            )

        if not user.is_active:
            raise SkillMatchException(
                statuscode=status.HTTP_403_FORBIDDEN,
                message="La cuenta de usuario se encuentra suspendida o inactiva."
            )

        if user.is_locked:
            raise SkillMatchException(
                statuscode=status.HTTP_423_LOCKED,
                message="La cuenta de usuario se encuentra bloqueada por motivos de seguridad."
            )

        # ROTACIÓN DE TOKEN: Revocar el Refresh Token anterior para impedir reuso
        revoke_token(clean_token)

        # Emitir nuevo par de tokens preservando estrictamente el rol dinámico
        new_access_token = create_access_token(
            subject=str(user.id),
            role=user.role.value
        )
        new_refresh_token = create_refresh_token(
            subject=str(user.id),
            role=user.role.value
        )

        return TokenRefreshResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )

    @staticmethod
    def logout(access_token: str, refresh_token: Optional[str] = None) -> None:
        """
        Revoca inmediatamente el token de acceso actual y opcionalmente el token de refresco.
        """
        if access_token:
            clean_access = access_token.replace("Bearer ", "").strip()
            revoke_token(clean_access)

        if refresh_token:
            revoke_token(refresh_token.strip())

    @staticmethod
    def get_current_user_profile(user: User) -> UserMeResponse:
        """
        Mapea el modelo User a la respuesta pública de identidad y perfil unificado.
        """
        return UserMeResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role.value,
            is_active=user.is_active,
            avatar_url=user.avatar_url,
            phone_number=user.phone_number,
            provider=user.provider
        )
