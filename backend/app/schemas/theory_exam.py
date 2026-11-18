from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.theory_question import Choice


class TheoryStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evaluation_id: UUID
    level_number: int = Field(ge=1, le=5)


class TheoryStartResponse(BaseModel):
    evaluation_id: UUID
    level_number: int
    status: str
    question_count: int
    started_at: datetime
    deadline_at: datetime


class PublicTheoryQuestion(BaseModel):
    id: UUID
    version: int
    position: int
    kind: str
    prompt: str
    choices: list[Choice]
    time_limit_seconds: int
    max_score: float
