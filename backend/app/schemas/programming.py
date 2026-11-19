from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChallengeTestCaseInput(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    name: str = Field(min_length=1, max_length=120)
    stdin_data: str = Field(default="", max_length=100_000)
    expected_stdout: str = Field(max_length=100_000)
    visibility: Literal["PUBLIC", "HIDDEN"] = "HIDDEN"
    order_index: int = Field(ge=0, le=10_000)


class ChallengeCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill_id: UUID
    challenge_type_id: UUID | None = None
    level_number: int = Field(ge=1, le=5)
    title: str = Field(min_length=3, max_length=160)
    statement: str = Field(min_length=10, max_length=20_000)
    evaluation_modality: Literal["SANDBOX", "SPREADSHEET"] = "SANDBOX"
    execution_profile: str = Field(default="PYTHON_3_12", min_length=1, max_length=40)
    starter_code: str = Field(default="", max_length=50_000)
    time_limit_ms: int = Field(default=2_000, ge=100, le=30_000)
    memory_limit_mb: int = Field(default=128, ge=16, le=1_024)
    max_output_bytes: int = Field(default=65_536, ge=1_024, le=1_048_576)
    allowed_imports: list[str] = Field(default_factory=list, max_length=100)
    blocked_imports: list[str] = Field(default_factory=list, max_length=100)
    tests: list[ChallengeTestCaseInput] = Field(min_length=1, max_length=100)

    @field_validator("allowed_imports", "blocked_imports")
    @classmethod
    def validate_import_names(cls, values: list[str]) -> list[str]:
        for value in values:
            if not value or len(value) > 100 or not value.replace(".", "").replace("_", "").isalnum():
                raise ValueError("La lista de imports contiene un nombre inválido.")
        return sorted(set(values))


class ChallengePreviewRequest(ChallengeCreateRequest):
    code: str = Field(min_length=1, max_length=100_000)


class ChallengeSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    skill_id: UUID
    challenge_type_id: UUID | None
    level_number: int
    version: int
    title: str
    evaluation_modality: str
    execution_profile: str
    status: str
    time_limit_ms: int
    memory_limit_mb: int
    max_output_bytes: int
    published_at: datetime | None


class ChallengeResponse(ChallengeSummary):
    statement: str
    starter_code: str
    allowed_imports: list[str]
    tests: list[ChallengeTestCaseInput]


class ChallengeRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=100_000)


class ChallengeTestResult(BaseModel):
    name: str
    passed: bool
    stdout: str
    stderr: str
    exit_code: int | None
    timed_out: bool


class ChallengeRunResponse(BaseModel):
    challenge_id: UUID
    passed_tests: int
    total_tests: int
    status: Literal["PASSED", "FAILED", "REJECTED", "ERROR"]
    results: list[ChallengeTestResult]


class ChallengeSubmissionResponse(ChallengeRunResponse):
    submission_id: UUID
    submitted_at: datetime
