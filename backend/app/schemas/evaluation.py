from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class EvaluationConsentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    biometric_consent: Literal[True]
    integrity_consent: Literal[True]
    attempt_rule_accepted: Literal[True]
    policy_version: str


class EvaluationPreflightResponse(BaseModel):
    teaching_skill_id: UUID
    skill_name: str
    syllabus: str
    requirements: list[str]
    stages: list[str]
    estimated_duration_minutes: int | None = None
    free_evaluations_left: int
    attempts_used: int
    policy_version: str
    pending_evaluation_id: UUID | None = None


class EvaluationConsentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    status: str
    biometric_consent_at: datetime
    policy_version: str
    started_at: datetime | None
