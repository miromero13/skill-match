"""Bounded metadata only: clipboard contents and arbitrary context are forbidden."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

IncidentKind = Literal["AWAY", "RETURN", "COPY", "CUT", "PASTE", "DROP", "CONTEXT_MENU",
                       "FULLSCREEN_EXIT", "OFFLINE", "ONLINE", "PAGE_EXIT", "SESSION_OPEN", "SESSION_RESUME"]


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
