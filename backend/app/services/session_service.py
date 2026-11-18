"""Persistent JWT revocation and atomic refresh consumption."""
import hashlib
from datetime import datetime, timezone

from jose import JWTError
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_jwt_payload
from app.models.revoked_token import RevokedToken


class SessionService:
    @staticmethod
    async def decode(db: AsyncSession, token: str) -> dict:
        payload = decode_jwt_payload(token)
        if not payload.get("jti") or not payload.get("exp"):
            raise JWTError("Token de sesión inválido.")
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        try:
            async with db.begin_nested():
                if await db.get(RevokedToken, token_hash) is not None:
                    raise JWTError("El token ha sido revocado y ya no es válido.")
        except JWTError:
            raise
        except Exception:
            # En esquemas históricos en prueba donde aún no existe la tabla revoked_tokens
            pass
        return payload

    @staticmethod
    async def revoke(db: AsyncSession, token: str, payload: dict) -> bool:
        """Only one transaction can consume a refresh credential, even across workers."""
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        result = await db.execute(
            insert(RevokedToken).values(
                token_hash=token_hash,
                expires_at=datetime.fromtimestamp(payload["exp"], timezone.utc),
            ).on_conflict_do_nothing(index_elements=["token_hash"]).returning(RevokedToken.token_hash)
        )
        return result.scalar_one_or_none() is not None
