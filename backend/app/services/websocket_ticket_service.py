"""Short-lived, signed handshake tickets for HU-24 WebSocket connections."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from jose import jwt

from app.core.config import settings
from app.models.user import UserRole


@dataclass(frozen=True, slots=True)
class WebSocketTicketIdentity:
    user_id: UUID
    role: str
    jti: str


class WebSocketTicketService:
    @staticmethod
    def issue(*, user_id: UUID, role: UserRole | str) -> str:
        canonical_role = UserRole(role).value
        now = datetime.now(timezone.utc)
        claims = {
            "sub": str(user_id),
            "role": canonical_role,
            "type": "websocket",
            "iat": now,
            "exp": now + timedelta(seconds=settings.WS_TICKET_EXPIRE_SECONDS),
            "jti": str(uuid4()),
        }
        return jwt.encode(
            claims,
            settings.SECRET_KEY.get_secret_value(),
            algorithm=settings.ALGORITHM,
        )

    @staticmethod
    def validate(ticket: str) -> WebSocketTicketIdentity:
        if not isinstance(ticket, str) or not ticket.strip():
            raise ValueError("Ticket WebSocket inválido.")
        claims = jwt.decode(
            ticket,
            settings.SECRET_KEY.get_secret_value(),
            algorithms=[settings.ALGORITHM],
        )
        if claims.get("type") != "websocket":
            raise ValueError("El token no es un ticket WebSocket.")
        user_id = UUID(str(claims.get("sub", "")))
        role = UserRole(claims.get("role")).value
        jti = claims.get("jti")
        issued_at = claims.get("iat")
        expires_at = claims.get("exp")
        if not isinstance(jti, str) or not jti:
            raise ValueError("Ticket WebSocket sin identificador.")
        if not isinstance(issued_at, (int, float)) or not isinstance(expires_at, (int, float)):
            raise ValueError("Ticket WebSocket sin vigencia válida.")
        if expires_at <= issued_at:
            raise ValueError("Ticket WebSocket con vigencia inválida.")
        return WebSocketTicketIdentity(user_id=user_id, role=role, jti=jti)
