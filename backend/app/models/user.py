import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Boolean, Integer, DateTime, Text, JSON, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user_learning_skill import UserLearningSkill
    from app.models.user_availability import UserAvailability
    from app.models.wallet import Wallet


class UserRole(str, Enum):
    """
    Roles canónicos del sistema SkillMatch (estrictamente dos).
    - MEMBER: Miembro de la comunidad (autenticado por Google, sin contraseña).
    - ADMIN: Administrador de la plataforma (autenticado por correo y contraseña).
    """
    MEMBER = "MEMBER"
    ADMIN = "ADMIN"


class ExchangeModality(str, Enum):
    """Modalidad de intercambio preferida por el miembro (RF-USR-09)."""
    VIRTUAL = "VIRTUAL"
    PRESENCIAL = "PRESENCIAL"
    BOTH = "BOTH"


class User(Base, TimestampMixin):
    """
    Entidad de persistencia de Usuarios.
    Soporta cuentas de Miembros y de Administradores con control de bloqueo de seguridad,
    datos de perfil extendido, preferencias de modalidad y biometría facial.
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

    # Campos complementarios para miembros (Google OAuth - HU-07)
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
        comment="google | institutional"
    )
    provider_user_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        default=None
    )

    # Campos de Perfil Personal, Preferencias y Modalidad
    bio: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        default=None,
        comment="Biografía y presentación del miembro",
    )
    languages: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=lambda: ["Español"],
        comment="Lista de idiomas hablados por el miembro",
    )
    timezone: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="America/La_Paz",
    )
    links: Mapped[dict[str, str]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment="Enlaces externos del perfil (github, linkedin, portfolio, website)",
    )
    exchange_modality: Mapped[ExchangeModality] = mapped_column(
        String(20),
        nullable=False,
        default=ExchangeModality.VIRTUAL,
    )
    presencial_radius_km: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=10,
        comment="Radio geográfico en km para encuentros presenciales (0 a 500)",
    )
    location_label: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        default=None,
        comment="Ciudad o zona de referencia para clases presenciales",
    )
    latitude: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        default=None,
        comment="Latitud geográfica aproximada para cálculo de cercanía",
    )
    longitude: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        default=None,
        comment="Longitud geográfica aproximada para cálculo de cercanía",
    )
    buffer_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=15,
        comment="Buffer de descanso en minutos entre sesiones agendadas",
    )
    gcal_synced: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    gcal_calendar_email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        default=None,
    )

    # Campos de biometría facial oficial
    biometric_embedding: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        default=None,
        comment="Vector numérico de características faciales (128-d) serializado localmente",
    )
    biometric_enrolled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )
    biometric_face_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        default=None,
        comment="Hash SHA-256 determinístico del vector biométrico registrado",
    )

    # Campos de Verificación de Identidad con Carnet (CI/DNI) 100% Automática
    identity_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="NOT_VERIFIED",
        server_default="NOT_VERIFIED",
        comment="Estado de verificación de identidad: NOT_VERIFIED, VERIFIED, REJECTED",
    )
    id_document_number: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        default=None,
        comment="Número de carnet de identidad o DNI verificado",
    )
    id_document_type: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
        default="CI",
        comment="Tipo de documento de identidad oficial (CI/DNI)",
    )
    id_face_similarity_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        default=None,
        comment="Puntaje de similitud coseno entre foto del carnet y rostro en vivo (0.0 a 1.0)",
    )
    identity_verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        comment="Marca de tiempo UTC de la verificación exitosa de identidad",
    )
    identity_rejection_reason: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        default=None,
        comment="Motivo explicativo en caso de rechazo de identidad",
    )

    wallet: Mapped[Optional["Wallet"]] = relationship("Wallet", lazy="selectin", uselist=False)

    # Relación con demandas de aprendizaje (HU-15)
    learning_skills: Mapped[list["UserLearningSkill"]] = relationship(
        "UserLearningSkill",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    # Relación con disponibilidad semanal
    availabilities: Mapped[list["UserAvailability"]] = relationship(
        "UserAvailability",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}', role='{self.role}', is_locked={self.is_locked})>"
