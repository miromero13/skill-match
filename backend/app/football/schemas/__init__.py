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
    confirmed_chunks: list[int] = Field(default_factory=list)


class EnvCheckRequest(BaseModel):
    brightness: float = Field(..., ge=0.0, le=255.0)
    noise_db: float = Field(..., ge=0.0, le=140.0)
    face_detected: bool
    ball_detected: bool
    latency_ms: float = Field(default=50.0, ge=0.0)


class EnvCheckResponse(BaseModel):
    session_id: UUID
    passed: bool
    estado: str
    failures: list[str] = Field(default_factory=list)


class LivenessRequest(BaseModel):
    challenge_passed: bool
    gesture_code: str = Field(default="head_nod", min_length=1, max_length=50)
    confidence: float = Field(default=0.95, ge=0.0, le=1.0)


class LivenessResponse(BaseModel):
    session_id: UUID
    passed: bool
    estado: str


class CalibrationRequest(BaseModel):
    client_touch_timestamp_ms: int = Field(..., ge=0)
    estimated_ball_radius_px: float | None = Field(default=None, gt=0.0)


class CalibrationResponse(BaseModel):
    session_id: UUID
    client_touch_timestamp_ms: int
    estado: str


class ChunkUploadResponse(BaseModel):
    session_id: UUID
    chunk_index: int
    sha256: str
    size_bytes: int
    storage_uri: str
    idempotent_replay: bool
    estado: str


class FinalizeSessionRequest(BaseModel):
    expected_chunks: int | None = Field(default=None, ge=1)
    duration_seconds: float | None = Field(default=None, gt=0.0)
    fps: float | None = Field(default=30.0, gt=0.0)


class FinalizeSessionResponse(BaseModel):
    session_id: UUID
    estado: str
    assembled_uri: str
    assembled_sha256: str
    assembled_size_bytes: int
    total_chunks: int
    task_id: str | None = None


class FraudIncidentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tipo: str
    severidad: str
    t_ms: int
    detalle: str | None = None


class ValidationMetricsRead(BaseModel):
    toques: int
    racha: int
    toques_por_minuto: float
    altura_media: float
    regularidad: float
    bote_count: int
    cumplimiento_por_tramo: list[ChallengeSegmentRead] = Field(default_factory=list)


class ValidationResultResponse(BaseModel):
    session_id: UUID
    estado: str
    nivel: str
    probabilidades: dict[str, float]
    confianza: float
    metricas: ValidationMetricsRead
    coherencia_audio_video: float
    puntaje_1_100: float
    puntaje_calibrado: bool
    puntaje_riesgo: float
    incidencias: list[FraudIncidentRead] = Field(default_factory=list)
    retroalimentacion: dict[str, list[str]]
    requiere_revision: bool
    version_modelo: str
    version_config: str


class WSClientMessage(BaseModel):
    type: Literal["client_event", "ping", "next_command"]
    event: Literal["tab_hidden", "focus_lost", "fullscreen_exit"] | None = None
    segment_index: int | None = None
    timestamp_ms: int | None = None
    payload: dict[str, Any] | None = None


class WSServerMessage(BaseModel):
    type: Literal["command", "status", "progress", "result_ready", "pong"]
    session_id: UUID
    data: dict[str, Any] = Field(default_factory=dict)
