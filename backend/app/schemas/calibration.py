from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CalibrationChallengeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    action: Literal["TURN_LEFT", "TURN_RIGHT"]
    expires_at: datetime


class SpokenVideoFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")
    time_ms: float = Field(ge=0, le=10000, allow_inf_nan=False)
    image: str = Field(min_length=1, max_length=80000)


class CalibrationVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    challenge_id: UUID
    frames: list[Annotated[str, Field(min_length=1, max_length=200_000)]] = Field(min_length=3, max_length=12)
    audio_samples: list[Annotated[float, Field(ge=-1, le=1, allow_inf_nan=False)]] = Field(min_length=112000, max_length=160000)
    spoken_frames: list[SpokenVideoFrame] = Field(min_length=20, max_length=100)
    ambient_audio_samples: list[Annotated[float, Field(ge=-1, le=1, allow_inf_nan=False)]] = Field(min_length=32000, max_length=64000)
    camera_label: str = Field(default="", max_length=200)


class CalibrationStateResponse(BaseModel):
    evaluation_id: UUID
    ready: bool
    status: str
    started_at: datetime | None
    checks: dict[str, bool]
