from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator

from app.models.user import ExchangeModality


ALLOWED_BUFFER_MINUTES = {0, 10, 15, 30, 60}


class UserProfileUpdate(BaseModel):
    """Esquema de actualización integral del perfil personal y preferencias (PUT /api/users/me/profile)."""
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    bio: Optional[str] = Field(default=None, max_length=1000)
    avatar_url: Optional[str] = Field(default=None, max_length=500)
    languages: list[str] = Field(default_factory=list, max_length=15)
    timezone: str = Field(default="America/La_Paz", min_length=2, max_length=100)
    links: dict[str, str] = Field(default_factory=dict)
    exchange_modality: ExchangeModality = Field(default=ExchangeModality.VIRTUAL)
    presencial_radius_km: int = Field(default=10, ge=0, le=500)
    location_label: Optional[str] = Field(default=None, max_length=255)
    buffer_minutes: int = Field(default=15)
    gcal_synced: bool = Field(default=False)
    gcal_calendar_email: Optional[str] = Field(default=None, max_length=255)

    @field_validator("buffer_minutes")
    @classmethod
    def validate_buffer_minutes(cls, v: int) -> int:
        if v not in ALLOWED_BUFFER_MINUTES:
            raise ValueError(f"El buffer de descanso debe ser uno de {sorted(ALLOWED_BUFFER_MINUTES)} minutos.")
        return v

    @field_validator("languages")
    @classmethod
    def clean_languages(cls, v: list[str]) -> list[str]:
        cleaned: list[str] = []
        for item in v:
            s = item.strip()
            if s and s not in cleaned:
                cleaned.append(s)
        return cleaned


class UserProfilePatch(BaseModel):
    """Esquema de actualización parcial del perfil (PATCH /api/users/me/profile)."""
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    bio: Optional[str] = Field(default=None, max_length=1000)
    avatar_url: Optional[str] = Field(default=None, max_length=500)
    languages: Optional[list[str]] = Field(default=None, max_length=15)
    timezone: Optional[str] = Field(default=None, min_length=2, max_length=100)
    links: Optional[dict[str, str]] = Field(default=None)
    exchange_modality: Optional[ExchangeModality] = Field(default=None)
    presencial_radius_km: Optional[int] = Field(default=None, ge=0, le=500)
    location_label: Optional[str] = Field(default=None, max_length=255)
    buffer_minutes: Optional[int] = Field(default=None)
    gcal_synced: Optional[bool] = Field(default=None)
    gcal_calendar_email: Optional[str] = Field(default=None, max_length=255)

    @field_validator("buffer_minutes")
    @classmethod
    def validate_buffer_minutes(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v not in ALLOWED_BUFFER_MINUTES:
            raise ValueError(f"El buffer de descanso debe ser uno de {sorted(ALLOWED_BUFFER_MINUTES)} minutos.")
        return v


class BiometricEnrollRequest(BaseModel):
    """Solicitud de captura y enrolamiento biométrico facial (POST /api/users/me/biometrics/enroll)."""
    image_base64: Optional[str] = Field(
        default=None,
        description="Imagen capturada del rostro en base64 (o data URL)",
    )
    frames: Optional[list[str]] = Field(
        default=None,
        description="Ráfaga de frames capturados en base64",
    )
    lighting_score: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Índice de iluminación medido en cámara (0.0 a 1.0)",
    )
    face_centered: bool = Field(
        default=True,
        description="Confirmación del encuadre oval centrado del rostro",
    )


class UserProfileResponse(BaseModel):
    """Respuesta consolidada del perfil de usuario e indicadores biométricos."""
    id: UUID
    user_id: UUID
    full_name: str
    email: str
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    languages: list[str] = Field(default_factory=list)
    timezone: str = "America/La_Paz"
    links: dict[str, str] = Field(default_factory=dict)
    exchange_modality: ExchangeModality = ExchangeModality.VIRTUAL
    presencial_radius_km: int = 10
    location_label: Optional[str] = None
    buffer_minutes: int = 15
    gcal_synced: bool = False
    gcal_calendar_email: Optional[str] = None
    has_biometric_enrollment: bool = False
    biometric_enrolled_at: Optional[datetime] = None
    biometric_face_hash: Optional[str] = None
    embedding_dimensions: Optional[int] = None

    model_config = {"from_attributes": True}
