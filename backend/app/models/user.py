import uuid
from datetime import datetime
from enum import Enum
from typing import Optional
from sqlalchemy import String, Boolean, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base, TimestampMixin

class UserRole(str, Enum):
    """
    Roles canónicos del sistema SkillMatch (estrictamente dos).
    - MEMBER: Miembro de la comunidad (autenticado por OAuth o OTP WhatsApp, sin contraseña).
    - ADMIN: Administrador de la plataforma (autenticado por correo y contraseña).
    """
    MEMBER = "MEMBER"
    ADMIN = "ADMIN"

class User(Base, TimestampMixin):
    """
    Entidad de persistencia de Usuarios.
    Soporta cuentas de Miembros y de Administradores con control de bloqueo de seguridad.
    """
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False
    )
    hashed_password: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        default=None,
        comment="Contraseña hasheada con bcrypt (exclusivo para rol ADMIN)"
    )
    full_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )
    role: Mapped[UserRole] = mapped_column(
        String(20),
        default=UserRole.MEMBER,
        nullable=False,
        index=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )

    # Campos de seguridad y bloqueo preventivo (RF-USR-16)
    is_locked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Indica si la cuenta administrativa está bloqueada preventivamente"
    )
    failed_login_attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Contador consecutivo de intentos de login fallidos (bloqueo al alcanzar 5)"
    )
    locked_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        comment="Timestamp hasta el cual la cuenta permanece bloqueada"
    )

    # Campos complementarios para miembros (OAuth / OTP WhatsApp - HU-07)
    phone_number: Mapped[Optional[str]] = mapped_column(
        String(30),
        unique=True,
        index=True,
        nullable=True,
        default=None
    )
    avatar_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        default=None
    )
    provider: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        default=None,
        comment="google | github | whatsapp | institutional"
    )
    provider_user_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        default=None
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}', role='{self.role}', is_locked={self.is_locked})>"
