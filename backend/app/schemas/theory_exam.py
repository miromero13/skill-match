from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.theory_question import Choice


class TheoryStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evaluation_id: UUID
    level_number: int | None = Field(default=None, ge=1, le=5)
    text_grading_consent: bool = False


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


class OralAnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    submission_id: UUID
    question_id: UUID
    audio_base64: str = Field(min_length=1, max_length=6400000)


class TheoryGradingResponse(BaseModel):
    evaluation_id: UUID
    state: str
    score: float | None = None
    max_score: float | None = None
    feedback: list[dict] | None = None
    provider: str | None = None
    model: str | None = None
    prompt_version: str | None = None


class TheoryProgressResponse(BaseModel):
    evaluation_id: UUID
    status: str
    question_count: int
    answered_count: int
    position: int
    server_time: datetime
    deadline_at: datetime
    question_deadline_at: datetime | None
    current_question: PublicTheoryQuestion | None
    grading_state: str = "PENDING"
    grading_score: float | None = None
    grading_feedback: list[dict] | None = None
    has_coding_stage: bool = False


class FinalEvaluationResponse(BaseModel):
    evaluation_id: UUID
    status: str
    passed: bool
    final_score: float
    theory_score: float
    theory_max_score: float
    theory_feedback: list[dict] | None = None
    has_coding_stage: bool = False
    sandbox_passed_tests: int | None = None
    sandbox_total_tests: int | None = None
    defense_transcript: str | None = None
    defense_score: float | None = None
    defense_feedback: str | None = None
    skill_validated: bool = False


class OralAnswerResponse(BaseModel):
    submission_id: UUID
    question_id: UUID
    transcript: str
    received_at: datetime
    status: str
