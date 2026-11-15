from typing import Optional
from uuid import UUID
from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


class DatasetSampleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    discipline: str = Field(min_length=1, max_length=50, description="Disciplina de captura (ej. música, fútbol, programación)")
    challenge: str = Field(min_length=1, max_length=100, description="Reto o habilidad evaluada")
    hardware_info: str = Field(min_length=1, max_length=255, description="Hardware y periféricos utilizados para la captura")
    signed_consent: bool = Field(default=True, description="Consentimiento explícito firmado")
    file_hash_sha256: Optional[str] = Field(default=None, description="Hash SHA-256 opcional precalculado por el cliente")

    @field_validator("discipline", "challenge", "hardware_info", mode="before")
    @classmethod
    def clean_text(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise ValueError("El campo no puede estar vacío.")
        return value

    @field_validator("signed_consent")
    @classmethod
    def require_explicit_consent(cls, value: bool) -> bool:
        if not value:
            raise ValueError("El consentimiento informado firmado es obligatorio.")
        return value

    @field_validator("file_hash_sha256")
    @classmethod
    def validate_hash_format(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            value = value.strip().lower()
            if len(value) != 64 or not all(c in "0123456789abcdef" for c in value):
                raise ValueError("El hash SHA-256 debe tener exactamente 64 caracteres hexadecimales.")
        return value


class DatasetSampleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    discipline: str
    challenge: str
    hardware_info: str
    signed_consent: bool
    file_format: str
    file_size_bytes: int
    file_hash_sha256: str
    storage_path: str
    uploaded_by_id: Optional[UUID] = None
    created_at: AwareDatetime
    updated_at: AwareDatetime
