"""Bounded metadata only: clipboard contents and arbitrary context are forbidden."""
from datetime import datetime
from typing import Annotated, Literal, Optional, get_args
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator

# One base64 JPEG frame (320x240 is ~20 KB); the cap keeps a 12-frame window under ~5 MB.
MAX_FRAME_B64_CHARS = 400_000

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
    "MODEL_UNAVAILABLE",
    "VIDEO_MISSING",
    "AUDIO_MISSING",
    "WINDOW_GAP",
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


GazeTarget = Literal["CENTER", "TOP_LEFT", "TOP_RIGHT", "BOTTOM_LEFT", "BOTTOM_RIGHT"]
GAZE_TARGETS: tuple[str, ...] = get_args(GazeTarget)


class GazeZoneModel(BaseModel):
    """Bounds of head pitch/yaw (degrees) and gaze_h/gaze_v while looking at the screen."""
    model_config = ConfigDict(extra="forbid")
    pitch_min: float
    pitch_max: float
    yaw_min: float
    yaw_max: float
    gaze_h_min: float
    gaze_h_max: float
    gaze_v_min: float
    gaze_v_max: float


class GazeCalibrationPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: GazeTarget
    frames: list[Annotated[str, StringConstraints(max_length=MAX_FRAME_B64_CHARS)]] = Field(min_length=1, max_length=6)


class GazeCalibrationRequest(TabRequest):
    """Frames captured while the candidate looks at the center and the four screen corners, one point each."""
    points: list[GazeCalibrationPoint] = Field(min_length=5, max_length=5)

    @model_validator(mode="after")
    def every_target_once(self):
        if sorted(point.target for point in self.points) != sorted(GAZE_TARGETS):
            raise ValueError("Hace falta exactamente un punto por cada objetivo de calibración.")
        return self


class GazeCalibrationResponse(BaseModel):
    zone: GazeZoneModel
    frames_used: int


class TrialResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    mode: Literal["TRIAL"] = "TRIAL"
    created_at: datetime
    expires_at: datetime
    closed_at: datetime | None
    lease_until: datetime | None
    event_count: int
    gaze_zone: GazeZoneModel | None = None


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
    frames: list[Annotated[str, StringConstraints(max_length=MAX_FRAME_B64_CHARS)]] = Field(
        default_factory=list, max_length=12)
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
