import logging
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import SkillMatchException
from app.core.security import verify_password, create_access_token, create_refresh_token
from app.models.user import User, UserRole
from app.schemas.admin_auth import AdminLoginRequest, AdminTokenData, AdminUserResponse

logger = logging.getLogger("skillmatch.admin_auth")

MAX_FAILED_ATTEMPTS = 5

class AdminAuthService:
    """
    Servicio de autenticación exclusivo para Administradores de SkillMatch.
    Implementa:
    - Verificación estricta de rol UserRole.ADMIN y estado activo (is_active).
    - Prevención de ataques de fuerza bruta con bloqueo preventivo tras 5 intentos fallidos (RF-USR-16).
    - Ofuscación y protección contra enumeración de cuentas.
    - Emisión de JWT con claim "role": "ADMIN".
    """

    @staticmethod
    async def authenticate_admin(
        db: AsyncSession,
        payload: AdminLoginRequest
    ) -> AdminTokenData:
        email = payload.email.lower().strip()

        # 1. Buscar usuario en base de datos
        result = await db.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()

        # 2. Protección contra enumeración y verificación de existencia
        if not user or user.role != UserRole.ADMIN:
            logger.warning(f"Intento de acceso administrativo fallido: email no registrado o rol no administrativo ({email})")
            raise SkillMatchException(
                statuscode=401,
                message="Credenciales administrativas inválidas o cuenta no autorizada."
            )

        # 3. Verificar si la cuenta administrativa está bloqueada preventivamente (RF-USR-16)
        if user.is_locked:
            logger.warning(f"Acceso denegado: cuenta administrativa {email} bloqueada por intentos fallidos.")
            raise SkillMatchException(
                statuscode=423,  # Locked
                message=(
                    "Cuenta administrativa bloqueada preventivamente tras 5 intentos fallidos consecutivos. "
                    "Contacte al equipo de seguridad de SkillMatch."
                )
            )

        # 4. Verificar si la cuenta está activa
        if not user.is_active:
            logger.warning(f"Acceso denegado: cuenta administrativa {email} inactiva.")
            raise SkillMatchException(
                statuscode=403,
                message="La cuenta administrativa se encuentra suspendida o inactiva."
            )

        # 5. Validar contraseña hasheada con bcrypt
        if not user.hashed_password or not verify_password(payload.password, user.hashed_password):
            user.failed_login_attempts += 1
            logger.warning(
                f"Contraseña errónea para administrador {email}. "
                f"Intento {user.failed_login_attempts}/{MAX_FAILED_ATTEMPTS}."
            )

            # Bloqueo preventivo al alcanzar los 5 intentos (RF-USR-16)
            if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
                user.is_locked = True
                user.locked_until = datetime.now(timezone.utc)
                await db.commit()
                logger.error(f"Cuenta administrativa {email} ha sido BLOQUEADA tras {MAX_FAILED_ATTEMPTS} intentos fallidos.")
                raise SkillMatchException(
                    statuscode=423,
                    message=(
                        "Cuenta administrativa bloqueada preventivamente tras superar el límite de 5 intentos fallidos. "
                        "Comuníquese con el administrador del sistema."
                    )
                )

            await db.commit()
            intentos_restantes = MAX_FAILED_ATTEMPTS - user.failed_login_attempts
            raise SkillMatchException(
                statuscode=401,
                message=(
                    f"Credenciales administrativas inválidas. "
                    f"Te quedan {intentos_restantes} intento(s) antes del bloqueo preventivo."
                )
            )

        # 6. Autenticación exitosa: reiniciar contador de fallos
        if user.failed_login_attempts > 0:
            user.failed_login_attempts = 0
            await db.commit()

        # 7. Generar tokens JWT con claim explícito role: "ADMIN"
        access_token = create_access_token(
            subject=str(user.id),
            role=UserRole.ADMIN.value
        )
        refresh_token = create_refresh_token(
            subject=str(user.id),
            role=UserRole.ADMIN.value
        )

        expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

        logger.info(f"Sesión administrativa iniciada exitosamente para: {user.email}")

        return AdminTokenData(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=expires_in,
            user=AdminUserResponse(
                id=user.id,
                email=user.email,
                full_name=user.full_name,
                role=user.role.value if hasattr(user.role, "value") else str(user.role),
                is_active=user.is_active,
                avatar_url=user.avatar_url
            )
        )
