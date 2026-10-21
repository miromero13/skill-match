from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
import bcrypt
from jose import jwt
from app.core.config import settings

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica si la contraseña coincide con su hash usando bcrypt nativo."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    """Genera el hash seguro bcrypt de la contraseña (exclusivo para rol ADMIN)."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def create_access_token(subject: str, role: str, expires_delta: Optional[timedelta] = None) -> str:
    """
    Crea un Access Token JWT con el claim dinámico obligatorio de rol ('MEMBER' o 'ADMIN').
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode: Dict[str, Any] = {
        "sub": str(subject),
        "role": str(role),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY.get_secret_value(),
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt

def create_refresh_token(subject: str, role: str) -> str:
    """Crea un Refresh Token JWT de mayor duración."""
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode: Dict[str, Any] = {
        "sub": str(subject),
        "role": str(role),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh",
    }
    return jwt.encode(
        to_encode,
        settings.SECRET_KEY.get_secret_value(),
        algorithm=settings.ALGORITHM
    )
