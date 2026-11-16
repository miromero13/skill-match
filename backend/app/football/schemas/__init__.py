from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreateValidationSessionRequest(BaseModel):
    skill_id: UUID | None = Field(
        default=None,
        description="Optional skill UUID for Football Ball Control validation",
    )


class ChallengeSegmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    indice: int
    tipo: Literal["LOW", "HIGH", "SLOW", "FAST"]
    inicio_servidor_ms: int
    duracion_ms: int
    cumplimiento: float | None = None
    latencia_reaccion_ms: int | None = None


class CreateValidationSessionResponse(BaseModel):
    session_id: UUID
    ws_url: str
    semilla: int
    intentos_restantes: int
    estado: str
    version_modelo: str
    version_config: str


class ValidationSessionStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    skill_id: UUID | None = None
    estado: str
    semilla: int
    creada_en: datetime
    finalizada_en: datetime | None = None
    version_modelo: str
    version_config: str
    segments: list[ChallengeSegmentRead] = Field(default_factory=list)


class WSClientMessage(BaseModel):
    type: Literal["client_event", "ping"]
    event: Literal["tab_hidden", "focus_lost", "fullscreen_exit"] | None = None
    timestamp_ms: int | None = None
    payload: dict[str, Any] | None = None


class WSServerMessage(BaseModel):
    type: Literal["command", "status", "progress", "result_ready", "pong"]
    session_id: UUID
    data: dict[str, Any] = Field(default_factory=dict)
