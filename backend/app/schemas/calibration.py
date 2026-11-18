from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CalibrationChallengeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    action: Literal["TURN_LEFT", "TURN_RIGHT"]
    expires_at: datetime


class CalibrationVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    challenge_id: UUID
    frames: list[Annotated[str, Field(min_length=1, max_length=200_000)]] = Field(min_length=3, max_length=12)
    audio_samples: list[Annotated[float, Field(ge=-1, le=1, allow_inf_nan=False)]] = Field(min_length=16, max_length=4096)
    camera_label: str = Field(default="", max_length=200)


class CalibrationStateResponse(BaseModel):
    evaluation_id: UUID
    ready: bool
    status: str
    started_at: datetime | None
    checks: dict[str, bool]
