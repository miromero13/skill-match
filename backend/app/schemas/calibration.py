from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.browser_supervision import GAZE_TARGETS, GazeTarget

MAX_CALIBRATION_FRAME_CHARS = 200_000  # one base64 JPEG
MAX_MOUTH_SAMPLES = 450  # ~15 readings per second over the 10 s speech segment, with margin


class CalibrationChallengeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    action: Literal["TURN_LEFT", "TURN_RIGHT"]
    expires_at: datetime


class SpokenVideoFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")
    time_ms: float = Field(ge=0, le=10000, allow_inf_nan=False)
    image: str = Field(min_length=1, max_length=80000)


class CalibrationGazePoint(BaseModel):
    """Frames captured while the member looks at one of the five screen targets (centre or a corner)."""
    model_config = ConfigDict(extra="forbid")
    target: GazeTarget
    frames: list[Annotated[str, Field(min_length=1, max_length=MAX_CALIBRATION_FRAME_CHARS)]] = Field(
        min_length=1, max_length=6)


class CalibrationMouthSample(BaseModel):
    """One browser mouth-aperture reading (same score as the server's); ``t_ms`` counts from the speech segment start."""
    model_config = ConfigDict(extra="forbid")
    t_ms: int = Field(ge=0, le=10_000, strict=True)
    mouth_open: float = Field(ge=0, le=2, allow_inf_nan=False)


class CalibrationVerifyRequest(BaseModel):
    """Evidence of the whole guided calibration: movement, the five gaze targets, silence and the spoken phrase.

    Every field is required: a request without the gaze points or the mouth telemetry is rejected (422), so the
    calibration can never become ready by omission.
    """
    model_config = ConfigDict(extra="forbid")
    challenge_id: UUID
    frames: list[Annotated[str, Field(min_length=1, max_length=MAX_CALIBRATION_FRAME_CHARS)]] = Field(min_length=3, max_length=12)
    gaze_points: list[CalibrationGazePoint] = Field(default_factory=list, max_length=5)
    audio_samples: list[Annotated[float, Field(ge=-1, le=1, allow_inf_nan=False)]] = Field(min_length=112000, max_length=160000)
    spoken_frames: list[SpokenVideoFrame] = Field(min_length=20, max_length=100)
    mouth_samples: list[CalibrationMouthSample] = Field(min_length=8, max_length=MAX_MOUTH_SAMPLES)
    ambient_audio_samples: list[Annotated[float, Field(ge=-1, le=1, allow_inf_nan=False)]] = Field(min_length=32000, max_length=64000)
    camera_label: str = Field(default="", max_length=200)

    @model_validator(mode="after")
    def evidence_is_coherent(self):
        if self.gaze_points and sorted(point.target for point in self.gaze_points) != sorted(GAZE_TARGETS):
            raise ValueError("Hace falta exactamente un punto por cada objetivo de calibración.")
        stamps = [sample.t_ms for sample in self.mouth_samples]
        duration_ms = len(self.audio_samples) * 1000 // 16_000
        if any(later - earlier < 30 for earlier, later in zip(stamps, stamps[1:])) or any(
                value > duration_ms for value in stamps):
            raise ValueError("mouth_samples debe ser creciente, a menos de ~33 muestras por segundo y dentro del audio.")
        return self


class CalibrationStateResponse(BaseModel):
    evaluation_id: UUID
    ready: bool
    status: str
    started_at: datetime | None
    checks: dict[str, bool]
