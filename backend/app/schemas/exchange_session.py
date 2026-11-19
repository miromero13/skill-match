from datetime import datetime
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SessionModality = Literal["VIRTUAL", "PRESENCIAL"]
SessionStatus = Literal["PENDING", "ACCEPTED", "REJECTED", "CANCELLED", "COMPLETED"]


class ExchangeSessionCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "match_id": "62be4604-5588-4f75-99df-8c4b747fd683",
                    "teaching_skill_id": "ef132d52-5748-471d-b890-31f749973f42",
                    "instructor_id": "13f172f2-df04-4495-b41a-66334e91db4f",
                    "starts_at": "2026-11-20T18:00:00Z",
                    "ends_at": "2026-11-20T19:00:00Z",
                    "timezone": "America/La_Paz",
                    "modality": "VIRTUAL",
                }
            ],
        },
    )

    match_id: UUID
    teaching_skill_id: UUID
    instructor_id: UUID
    starts_at: datetime
    ends_at: datetime
    timezone: str = Field(min_length=1, max_length=100)
    modality: SessionModality

    @field_validator("starts_at", "ends_at")
    @classmethod
    def require_aware_datetime(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("La fecha debe incluir zona horaria")
        return value

    @field_validator("timezone")
    @classmethod
    def require_iana_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Zona horaria IANA invalida") from exc
        return value

    @model_validator(mode="after")
    def validate_duration(self) -> "ExchangeSessionCreate":
        seconds = (self.ends_at - self.starts_at).total_seconds()
        if seconds < 60 or seconds > 3600:
            raise ValueError("La duracion debe estar entre 1 y 60 minutos")
        return self


class ExchangeSessionReschedule(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "starts_at": "2026-11-27T18:00:00Z",
                    "ends_at": "2026-11-27T19:00:00Z",
                }
            ]
        },
    )

    starts_at: datetime
    ends_at: datetime

    @field_validator("starts_at", "ends_at")
    @classmethod
    def require_aware_datetime(cls, value: datetime) -> datetime:
        return ExchangeSessionCreate.require_aware_datetime(value)

    @model_validator(mode="after")
    def validate_duration(self) -> "ExchangeSessionReschedule":
        seconds = (self.ends_at - self.starts_at).total_seconds()
        if seconds < 60 or seconds > 3600:
            raise ValueError("La duracion debe estar entre 1 y 60 minutos")
        return self


class ExchangeSessionCancel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "cancellation_reason": "Imprevisto familiar comunicado con anticipación",
                }
            ]
        },
    )

    cancellation_reason: str = Field(min_length=10, max_length=500)

    @field_validator("cancellation_reason")
    @classmethod
    def trim_reason(cls, value: str) -> str:
        trimmed = value.strip()
        if not 10 <= len(trimmed) <= 500:
            raise ValueError("El motivo debe tener entre 10 y 500 caracteres")
        return trimmed


class ExchangeSessionStatusUpdate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"examples": [{"status": "ACCEPTED"}]},
    )
    status: Literal["ACCEPTED", "REJECTED"]


class ExchangeSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    match_id: UUID
    teaching_skill_id: UUID
    created_by_id: UUID
    instructor_id: UUID
    learner_id: UUID
    starts_at: datetime
    ends_at: datetime
    timezone: str
    modality: SessionModality
    status: SessionStatus
    is_free: bool
    cancellation_reason: str | None = None
    cancelled_by_id: UUID | None = None
    cancelled_at: datetime | None = None
    quota_restored: bool
    booking_blocked_until: datetime | None = None
    actual_minutes: int | None = None
    completed_at: datetime | None = None
    can_confirm: bool = False
    can_report_noshow: bool = False
    my_confirmation: bool = False
    counterpart_confirmation: bool = False


class ExchangeSessionListResponse(BaseModel):
    items: list[ExchangeSessionResponse]
    free_sessions_left: int = Field(ge=0, le=2)
    free_sessions_limit: int = 2


class SessionCalendarExportResponse(BaseModel):
    filename: str
    content_type: Literal["text/calendar; charset=utf-8"]
    ics_content: str
    google_calendar_url: str


class SessionConfirmRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "request_key": "4dd85141-a45a-4aae-a507-2fa60d57b1cf",
                    "actual_minutes": 60,
                    "topics": ["Dependencias de FastAPI", "Sesiones asíncronas"],
                    "presence_pin": "7492",
                }
            ]
        },
    )

    request_key: UUID
    actual_minutes: int = Field(ge=1, le=60)
    topics: list[str] = Field(default_factory=list, max_length=10)
    presence_pin: str | None = None

    @field_validator("presence_pin")
    @classmethod
    def validate_pin_format(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if len(trimmed) != 4 or not trimmed.isdigit() or trimmed != value:
            raise ValueError("El PIN de presencia debe contener exactamente 4 dígitos numéricos")
        return trimmed

    @field_validator("topics")
    @classmethod
    def validate_topics(cls, value: list[str]) -> list[str]:
        if len(value) > 10:
            raise ValueError("No se pueden registrar más de 10 temas")
        normalized: list[str] = []
        for topic in value:
            t = topic.strip()
            if not 1 <= len(t) <= 120:
                raise ValueError("Cada tema debe tener entre 1 y 120 caracteres")
            normalized.append(t)
        return normalized


class SessionConfirmResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: UUID
    status: SessionStatus
    my_confirmation: bool
    counterpart_confirmation: bool
    actual_minutes: int | None = None
    completed_at: datetime | None = None
    escrow_release: Literal["NOT_APPLICABLE", "PENDING_HU42", "RELEASED"] = "NOT_APPLICABLE"


class SessionNoShowRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "request_key": "f95cb857-29c9-4b74-bab7-b5b7fdc91ebf",
                    "reason": "La contraparte no se presentó a la sesión ni respondió mensajes.",
                }
            ]
        },
    )

    request_key: UUID
    reason: str = Field(min_length=10, max_length=500)

    @field_validator("reason")
    @classmethod
    def trim_reason(cls, value: str) -> str:
        trimmed = value.strip()
        if not 10 <= len(trimmed) <= 500:
            raise ValueError("El motivo debe tener entre 10 y 500 caracteres")
        return trimmed


class SessionNoShowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: UUID
    reported_by_id: UUID
    absent_user_id: UUID
    reason: str
    status: Literal["PENDING_REPUTATION", "PROCESSED", "DISMISSED"] = "PENDING_REPUTATION"
    reported_at: datetime


class SessionPresencePinResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: UUID
    presence_pin: str
    expires_at: datetime
    attempt_count: int
    is_locked: bool
