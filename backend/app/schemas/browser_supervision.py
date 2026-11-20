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
    "HEAD_POSE_UP",
    "GAZE_AWAY",
    "GAZE_AWAY_UP",
    "GAZE_AWAY_DOWN",
    "GAZE_AWAY_LEFT",
    "GAZE_AWAY_RIGHT",
    "EYES_CLOSED",
    "CLIENT_MISMATCH",
    "VOICE_DETECTED",
    "MULTIPLE_SPEAKERS",
    "HIGH_NOISE",
    "DEVICE_DISCONNECTED",
    "STREAM_ERROR",
    "MODEL_UNAVAILABLE",
    "VIDEO_MISSING",
    "AUDIO_MISSING",
    "WINDOW_GAP",
    "FACE_OCCLUDED",
    "MOUTH_OCCLUDED",
    "CAMERA_BLOCKED",
    "VOICE_MISMATCH",
    "VOICE_UNVERIFIED",
    "LIP_SYNC_MISMATCH",
    "BACKGROUND_AUDIO",
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


MAX_VOICE_SAMPLES = 192_000  # 12 s at 16 kHz


class MouthSampleRequest(BaseModel):
    """One mouth-aperture reading while the control phrase is read; ``t_ms`` counts from the recording start."""
    model_config = ConfigDict(extra="forbid")
    t_ms: int = Field(ge=0, le=12_000, strict=True)
    mouth_open: float = Field(ge=0, le=2)


class VoiceCalibrationFrame(BaseModel):
    """A JPEG sampled while recording; ``t_ms`` counts from the start of ``audio_samples``. The server measures the
    mouth on these itself to cross-check the browser's mouth readings."""
    model_config = ConfigDict(extra="forbid")
    t_ms: int = Field(ge=0, le=12_000, strict=True)
    image: str = Field(min_length=1, max_length=80_000)


class VoiceCalibrationRequest(TabRequest):
    """16 kHz mono audio: ``ambient_ms`` of silence first, then the candidate reading the control phrase.

    ``frames`` (20 to 130 sampled JPEGs) are required: without server frames the mouth telemetry cannot be verified.
    """
    audio_samples: list[float] = Field(min_length=1, max_length=MAX_VOICE_SAMPLES)
    ambient_ms: int = Field(ge=500, le=3000, strict=True)
    mouth_samples: list[MouthSampleRequest] = Field(default_factory=list, max_length=450)
    frames: list[VoiceCalibrationFrame] = Field(min_length=20, max_length=130)

    @model_validator(mode="after")
    def mouth_is_coherent(self):
        stamps = [sample.t_ms for sample in self.mouth_samples]
        duration_ms = len(self.audio_samples) * 1000 // 16_000
        if any(later - earlier < 30 for earlier, later in zip(stamps, stamps[1:])) or any(
                value > duration_ms for value in stamps):
            raise ValueError("mouth_samples debe ser creciente, a menos de ~33 muestras por segundo y dentro del audio.")
        frame_stamps = [frame.t_ms for frame in self.frames]
        if any(later - earlier < 40 for earlier, later in zip(frame_stamps, frame_stamps[1:])) or any(
                value > duration_ms for value in frame_stamps):
            raise ValueError("frames debe ser creciente, a menos de 25 imágenes por segundo y dentro del audio.")
        return self


class VoiceCalibrationResponse(BaseModel):
    voice_enrolled: bool
    voiced_seconds: float


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
    voice_enrolled: bool = False  # the embedding itself is never exposed


class IncidentResponse(IncidentRequest):
    model_config = ConfigDict(from_attributes=True)
    sequence: int
    received_at: datetime


class BatchResponse(BaseModel):
    accepted_ids: list[UUID]
    event_count: int


class GazeSampleRequest(BaseModel):
    """One browser reading (MediaPipe in the page, ~15 fps) of where the candidate looks; ``t_ms`` is the offset
    from the window's ``observed_at``. The server only uses it when it agrees with its own frame measurements."""
    model_config = ConfigDict(extra="forbid")
    t_ms: int = Field(ge=0, le=30000, strict=True)
    head_pitch: Optional[float] = Field(default=None, ge=-180, le=180)
    head_yaw: Optional[float] = Field(default=None, ge=-180, le=180)
    gaze_h: Optional[float] = Field(default=None, ge=-2, le=2)
    gaze_v: Optional[float] = Field(default=None, ge=-2, le=2)
    blink: bool
    face_count: int = Field(ge=0, le=10, strict=True)
    # Mouth aperture score, same formula as the server's ``mouth_open_score`` (see gaze-tracking.ts).
    mouth_open: Optional[float] = Field(default=None, ge=0, le=2)


class AVWindowRequest(TabRequest):
    window_id: UUID
    observed_at: AwareDatetime
    duration_ms: int = Field(default=2500, ge=500, le=30000, strict=True)
    mode: Literal["QUIET", "SPEAKING", "UNIFIED"] = "UNIFIED"
    frames: list[Annotated[str, StringConstraints(max_length=MAX_FRAME_B64_CHARS)]] = Field(
        default_factory=list, max_length=12)
    audio_samples: Optional[list[float]] = Field(default=None, max_length=160000)
    # Capture offset (ms from observed_at) of each frame, aligned with ``frames``.
    frame_times_ms: Optional[list[Annotated[int, Field(ge=0, le=30000, strict=True)]]] = Field(
        default=None, max_length=12)
    gaze_samples: list[GazeSampleRequest] = Field(default_factory=list, max_length=60)
    # Tuning label (T11): only used by the opt-in diagnostics log, never stored in the ledger.
    label: Optional[str] = Field(default=None, min_length=1, max_length=40, pattern=r"^[a-z0-9_-]+$")

    @model_validator(mode="after")
    def timestamps_are_coherent(self):
        times = self.frame_times_ms
        if times is not None:
            if len(times) != len(self.frames):
                raise ValueError("frame_times_ms debe tener un valor por cada frame.")
            if any(later < earlier for earlier, later in zip(times, times[1:])) or any(
                    value > self.duration_ms for value in times):
                raise ValueError("frame_times_ms debe ser creciente y caer dentro de la ventana.")
        stamps = [sample.t_ms for sample in self.gaze_samples]
        if any(later - earlier < 30 for earlier, later in zip(stamps, stamps[1:])) or any(
                value > self.duration_ms for value in stamps):
            raise ValueError("gaze_samples debe ser creciente, a menos de ~33 muestras por segundo y dentro de la ventana.")
        return self


class OcclusionResponse(BaseModel):
    face: bool = False
    mouth: bool = False


class AVWindowResponse(BaseModel):
    window_id: UUID
    face_count: int
    head_orientation: Literal["CENTER", "DOWN", "UP", "LEFT", "RIGHT", "UNKNOWN"]
    identity_match: Optional[bool]
    speech_detected: bool
    mouth_moving: bool = False
    mouth_sync: Optional[bool] = None  # kept for compatibility: ``lip_sync == "synced"`` when a verdict exists
    # Voice ownership (the voice is the enrolled one) and temporal voice/mouth correlation; null = no speech or no verdict.
    voice_match: Optional[bool] = None
    lip_sync: Optional[Literal["synced", "unsynced", "insufficient"]] = None
    multiple_speakers: bool = False
    noise_level: float
    # Confirmed (continuous >= 1 s) covered face / covered mouth and blocked or frozen camera (S7, S8).
    occlusion: OcclusionResponse = Field(default_factory=OcclusionResponse)
    camera_blocked: bool = False
    anomalies: list[str]
    incidents_created: list[IncidentResponse]
