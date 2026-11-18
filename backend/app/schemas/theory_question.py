"""Administrative question content; never use this schema in member responses."""
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class Choice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: Annotated[Text, Field(max_length=8)]
    text: Annotated[Text, Field(max_length=1000)]


class Criterion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Annotated[Text, Field(max_length=100)]
    weight: float = Field(gt=0, le=100, allow_inf_nan=False)
    description: Annotated[Text, Field(max_length=2000)]


class QuestionContent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["OPEN", "MULTIPLE_CHOICE", "TRUE_FALSE"] = "OPEN"
    prompt: Annotated[Text, Field(max_length=4000)]
    choices: list[Choice] = Field(default_factory=list, max_length=6)
    correct_choice: str | None = Field(default=None, max_length=8)
    reference_answer: str = Field(default="", max_length=8000)
    criteria: list[Criterion] = Field(default_factory=list, max_length=12)
    time_limit_seconds: int = Field(default=90, ge=1, le=300)
    max_score: float = Field(default=20, gt=0, le=100, allow_inf_nan=False)


class QuestionCreate(QuestionContent):
    skill_id: UUID
    level_number: int = Field(ge=1, le=5)


class QuestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    version: int
    skill_id: UUID
    level_number: int
    status: Literal["DRAFT", "PUBLISHED", "ARCHIVED"]
    content: QuestionContent
