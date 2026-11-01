import base64
import json
import logging
from typing import Optional
from uuid import UUID
import httpx
from fastapi import status
from jose import jwt, JWTError

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
from app.models.user import User, UserRole
from app.schemas.auth import (
    TokenRefreshResponse,
    UserMeResponse,
    AuthTokenResponse,
)

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
            role=user.role.value if hasattr(user.role, "value") else str(user.role),
            is_active=user.is_active,
            avatar_url=user.avatar_url,
            phone_number=user.phone_number,
            provider=user.provider
        )

    @staticmethod
    async def authenticate_with_google(
        db: AsyncSession,
        id_token_str: str
    ) -> AuthTokenResponse:
        """
        Autentica o provisiona Just-In-Time (JIT) a un Miembro de la comunidad vía Google OAuth.
        Valida el id_token provisto y emite el par de tokens JWT con claim 'role': 'MEMBER'.
        """
        if not id_token_str or not id_token_str.strip():
            raise SkillMatchException(
                statuscode=status.HTTP_400_BAD_REQUEST,
                message="El token de Google (id_token) es obligatorio."
            )

        token = id_token_str.strip()

        # Decodificación y validación del Google ID Token
        google_user_info: dict = {}
        verified = False

        # 1. Intentar validar primero con Google tokeninfo oficial (Online)
        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
                resp = await client.get(
                    f"https://oauth2.googleapis.com/tokeninfo?id_token={token}"
                )
                if resp.status_code == 200:
                    payload = resp.json()
                    # Si GOOGLE_CLIENT_ID está configurado (y no es el placeholder), validar aud
                    configured_client_id = settings.GOOGLE_CLIENT_ID
                    if configured_client_id and "tu-google-client-id" not in configured_client_id:
                        if payload.get("aud") != configured_client_id:
                            raise SkillMatchException(
                                statuscode=status.HTTP_401_UNAUTHORIZED,
                                message="El token de Google no corresponde al Client ID autorizado de SkillMatch."
                            )
                    google_user_info = {
                        "sub": payload.get("sub", ""),
                        "email": payload.get("email"),
                        "name": payload.get("name", payload.get("email", "").split("@")[0]),
                        "picture": payload.get("picture"),
                    }
                    verified = True
                else:
                    logger.warning(f"Google tokeninfo online rechazó el token (HTTP {resp.status_code}): {resp.text}")
        except SkillMatchException:
            raise
        except httpx.RequestError as exc:
            logger.warning(f"Error de red contactando Google tokeninfo: {exc}")

        # 2. Modo desarrollo / pruebas / token simulado: Si no se pudo verificar online pero estamos en dev
        if not verified and (settings.ENVIRONMENT == "development" or settings.DEBUG):
            # Intentar decodificar con base64 seguro tolerando codificaciones UTF-8 / latin-1
            try:
                parts = token.split(".")
                if len(parts) >= 2:
                    payload_b64 = parts[1]
                    # Ajustar padding de Base64 si falta
                    payload_b64 += "=" * ((4 - len(payload_b64) % 4) % 4)
                    raw_bytes = base64.urlsafe_b64decode(payload_b64.encode("ascii"))
                    decoded_str = raw_bytes.decode("utf-8", errors="replace")
                    claims = json.loads(decoded_str)

                    if claims.get("email"):
                        google_user_info = {
                            "sub": claims.get("sub", ""),
                            "email": claims.get("email"),
                            "name": claims.get("name") or claims.get("email", "").split("@")[0],
                            "picture": claims.get("picture"),
                        }
                        verified = True
                        logger.info(f"Token de Google verificado en modo desarrollo/simulación para: {claims.get('email')}")
            except Exception as e:
                logger.warning(f"Fallo al decodificar token en modo desarrollo: {e}")


        if not verified or not google_user_info.get("email"):
            raise SkillMatchException(
                statuscode=status.HTTP_401_UNAUTHORIZED,
                message="Token de Google inválido, expirado o no verificable. Por favor intente nuevamente."
            )

        email = google_user_info["email"].lower().strip()
        sub = google_user_info.get("sub")
        name = google_user_info.get("name") or email.split("@")[0]
        picture = google_user_info.get("picture")

        # Buscar usuario por correo electrónico
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user:
            # Validación de estado
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

            # Actualizar datos de perfil de Google si aplica
            if not user.provider:
                user.provider = "google"
            if not user.provider_user_id and sub:
                user.provider_user_id = sub
            if picture and not user.avatar_url:
                user.avatar_url = picture
            await db.commit()
            await db.refresh(user)
        else:
            # JIT Provisioning (Just-In-Time) como MEMBER
            user = User(
                email=email,
                full_name=name,
                role=UserRole.MEMBER,
                is_active=True,
                is_locked=False,
                provider="google",
                provider_user_id=sub,
                avatar_url=picture,
                hashed_password=None, # Los miembros no poseen contraseña local
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            logger.info(f"Nuevo miembro provisionado exitosamente vía Google OAuth: {user.email} (ID: {user.id})")

        # Emitir tokens JWT con rol MEMBER
        access_token = create_access_token(
            subject=str(user.id),
            role=user.role.value if hasattr(user.role, "value") else str(user.role)
        )
        refresh_token = create_refresh_token(
            subject=str(user.id),
            role=user.role.value if hasattr(user.role, "value") else str(user.role)
        )

        user_profile = AuthService.get_current_user_profile(user)

        return AuthTokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user_profile
        )

