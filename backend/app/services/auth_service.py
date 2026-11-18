import time
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
)
from app.models.user import User, UserRole
from app.models.wallet import Wallet
from app.services.session_service import SessionService
from app.schemas.auth import (
    TokenRefreshResponse,
    UserMeResponse,
    AuthTokenResponse,
)

logger = logging.getLogger("skillmatch.services.auth")


class _GoogleCredentialRedaction(logging.Filter):
    """HTTPX logs request URLs at INFO; never expose a Google credential there."""
    def filter(self, record):
        if isinstance(record.args, tuple):
            record.args = tuple(
                value.copy_set_param("id_token", "[redacted]")
                if isinstance(value, httpx.URL) and value.host == "oauth2.googleapis.com" and "id_token" in value.params
                else value for value in record.args
            )
        return True


logging.getLogger("httpx").addFilter(_GoogleCredentialRedaction())


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
            payload = await SessionService.decode(db, clean_token)
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

        # Sign first: an issuance failure must not consume the existing credential.
        role = UserRole(user.role).value
        new_access_token = create_access_token(subject=str(user.id), role=role)
        new_refresh_token = create_refresh_token(subject=str(user.id), role=role)
        if not await SessionService.revoke(db, clean_token, payload):
            raise SkillMatchException(statuscode=401, message="Refresh Token inválido o revocado.")
        await db.commit()

        return TokenRefreshResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )

    @staticmethod
    async def logout(db: AsyncSession, user: User, access_token: str, refresh_token: Optional[str] = None) -> None:
        """Validate ownership before atomically revoking either credential."""
        access = access_token.removeprefix("Bearer ").strip()
        access_payload = decode_jwt_payload(access)
        refresh_payload = None
        if refresh_token:
            refresh_token = refresh_token.strip()
            try:
                # An expired refresh cannot renew, but must not prevent access logout.
                refresh_payload = jwt.decode(
                    refresh_token, settings.SECRET_KEY.get_secret_value(),
                    algorithms=[settings.ALGORITHM], options={"verify_exp": False},
                )
            except JWTError:
                raise SkillMatchException(statuscode=401, message="Token de renovación inválido.")
            if refresh_payload.get("sub") != str(user.id) or refresh_payload.get("type") != "refresh":
                raise SkillMatchException(statuscode=401, message="El token de renovación no pertenece a esta sesión.")
        await SessionService.revoke(db, access, access_payload)
        if refresh_token and refresh_payload:
            await SessionService.revoke(db, refresh_token, refresh_payload)
        await db.commit()

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
            provider=user.provider,
            skill_points_balance=user.wallet.balance if user.wallet else 0,
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

        client_id = settings.GOOGLE_CLIENT_ID
        if not client_id or "tu-google-client-id" in client_id:
            raise SkillMatchException(statuscode=503, message="El acceso con Google no está configurado.")

        # Only Google's verification endpoint may establish the token's identity.
        # Never decode an unverified credential, even in debug/development.
        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
                response = await client.get(
                    "https://oauth2.googleapis.com/tokeninfo", params={"id_token": token}
                )
            claims = response.json() if response.status_code == 200 else {}
            verified = (
                isinstance(claims, dict)
                and claims.get("aud") == client_id
                and claims.get("iss") in ("accounts.google.com", "https://accounts.google.com")
                and claims.get("email_verified") in (True, "true")
                and isinstance(claims.get("sub"), str) and bool(claims["sub"].strip())
                and isinstance(claims.get("email"), str) and "@" in claims["email"]
                and int(claims.get("exp", 0)) > time.time()
            )
        except httpx.RequestError:
            raise SkillMatchException(statuscode=503, message="No se pudo verificar la identidad con Google. Intentá nuevamente.")
        except (ValueError, TypeError):
            verified = False

        if not verified:
            raise SkillMatchException(
                statuscode=401,
                message="Token de Google inválido, expirado o no verificable. Por favor intente nuevamente."
            )

        email = claims["email"].strip().lower()
        sub = claims["sub"]
        name = claims.get("name") or email.split("@")[0]
        picture = claims.get("picture")

        # Buscar usuario por correo electrónico
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user:
            role = user.role.value if isinstance(user.role, UserRole) else user.role
            if role != UserRole.MEMBER.value or (user.provider_user_id and user.provider_user_id != sub):
                raise SkillMatchException(statuscode=401, message="La identidad de Google no puede acceder a esta cuenta.")
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
                wallet=Wallet(balance=0),
            )
            db.add(user)
            await db.flush()
            user.wallet.user_id = user.id
            db.add(user.wallet)

        # Provision atomically with registration; never leave a member without a wallet.
        if user.wallet is None:
            user.wallet = Wallet(user_id=user.id, balance=0)
            db.add(user.wallet)
        await db.commit()
        await db.refresh(user)

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

