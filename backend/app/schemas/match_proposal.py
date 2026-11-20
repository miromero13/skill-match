from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, StringConstraints


class ProposalWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    starts_at: AwareDatetime
    replaces_proposal_id: UUID | None = None


class ProposalDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal_id: UUID


class ProposalResponse(BaseModel):
    id: UUID
    version: int
    starts_at: datetime
    status: Literal["pending", "superseded", "accepted", "declined"]
    proposed_by_you: bool
    contact_enabled: bool


class MessageWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class MessageResponse(BaseModel):
    id: UUID
    body: str
    sent_by_you: bool
    created_at: datetime
