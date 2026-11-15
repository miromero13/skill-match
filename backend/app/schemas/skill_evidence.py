from typing import Annotated
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import (
    AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl, UrlConstraints,
    ValidationInfo, field_validator,
)

from app.models.skill_evidence import EvidenceType

EvidenceUrl = Annotated[HttpUrl, UrlConstraints(max_length=2048)]


class SkillEvidenceWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=150, strict=True)
    description: str | None = Field(default=None, max_length=2000, strict=True)
    url: EvidenceUrl
    evidence_type: EvidenceType

    @field_validator("title", "description", mode="before")
    @classmethod
    def normalize_text(cls, value: object, info: ValidationInfo) -> object:
        if isinstance(value, str):
            value = value.strip()
            if info.field_name == "description" and not value:
                return None
        return value

    @field_validator("url", mode="before")
    @classmethod
    def require_absolute_url_without_credentials(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            parts = urlsplit(value)
            if not parts.netloc or parts.scheme.lower() not in {"http", "https"}:
                raise ValueError("La URL debe ser absoluta y usar HTTP o HTTPS.")
            if "@" in parts.netloc:
                raise ValueError("La URL no debe incluir credenciales.")
        return value

    @field_validator("url")
    @classmethod
    def validate_normalized_url(cls, value: HttpUrl) -> HttpUrl:
        if value.username is not None or value.password is not None:
            raise ValueError("La URL no debe incluir credenciales.")
        if len(str(value)) > 2048:
            raise ValueError("La URL normalizada no debe superar 2048 caracteres.")
        return value


class SkillEvidenceCreate(SkillEvidenceWrite):
    """POST: campos editables, sin identificadores ni fechas del servidor."""


class SkillEvidenceUpdate(SkillEvidenceWrite):
    """PUT completo: description omitida se reemplaza por null."""


class SkillEvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    teaching_skill_id: UUID
    title: str
    description: str | None
    url: EvidenceUrl
    evidence_type: EvidenceType
    created_at: AwareDatetime
    updated_at: AwareDatetime
