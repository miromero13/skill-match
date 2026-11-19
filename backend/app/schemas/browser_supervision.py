"""Bounded metadata only: clipboard contents and arbitrary context are forbidden."""
from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

IncidentKind = Literal[
    "AWAY",
    "RETURN",
    "COPY",
    "CUT",
    "PASTE",
    "DROP",
    "CONTEXT_MENU",
    "FULLSCREEN_EXIT",
    "OFFLINE",
    "ONLINE",
    "PAGE_EXIT",
    "SESSION_OPEN",
    "SESSION_RESUME",
    "FACE_ABSENT",
    "MULTIPLE_FACES",
    "IDENTITY_MISMATCH",
    "HEAD_POSE_DOWN",
    "HEAD_POSE_SIDE",
    "VOICE_DETECTED",
    "MULTIPLE_SPEAKERS",
    "HIGH_NOISE",
    "DEVICE_DISCONNECTED",
    "STREAM_ERROR",
]


class TabRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tab_id: UUID


class TrialRequest(TabRequest):
    accepted: Literal[True]


class IncidentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: UUID
    kind: IncidentKind
    observed_at: AwareDatetime
    duration_ms: int = Field(default=0, ge=0, le=86_400_000, strict=True)


class IncidentBatch(TabRequest):
    events: list[IncidentRequest] = Field(min_length=1, max_length=50)


class TrialResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    mode: Literal["TRIAL"] = "TRIAL"
    created_at: datetime
    expires_at: datetime
    closed_at: datetime | None
    lease_until: datetime | None
    event_count: int


class IncidentResponse(IncidentRequest):
    model_config = ConfigDict(from_attributes=True)
    sequence: int
    received_at: datetime


class BatchResponse(BaseModel):
    accepted_ids: list[UUID]
    event_count: int


class AVWindowRequest(TabRequest):
    window_id: UUID
    observed_at: AwareDatetime
    duration_ms: int = Field(default=2500, ge=500, le=30000, strict=True)
    mode: Literal["QUIET", "SPEAKING", "UNIFIED"] = "UNIFIED"
    frames: list[str] = Field(default_factory=list, max_length=12)
    audio_samples: Optional[list[float]] = Field(default=None, max_length=160000)


class AVWindowResponse(BaseModel):
    window_id: UUID
    face_count: int
    head_orientation: Literal["CENTER", "DOWN", "LEFT", "RIGHT", "UNKNOWN"]
    identity_match: Optional[bool]
    speech_detected: bool
    mouth_moving: bool = False
    mouth_sync: Optional[bool] = None
    multiple_speakers: bool = False
    noise_level: float
    anomalies: list[str]
    incidents_created: list[IncidentResponse]
