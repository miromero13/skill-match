"""Contracts of the per-skill training lab (`/api/admin/skill-lab`)."""
from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

SampleRole = Literal["TRAINING", "REFERENCE"]


class MetricTypeResponse(BaseModel):
    code: str
    name: str
    description: str
    requires_target: bool
    requires_reference: bool


class SkillLabSampleResponse(BaseModel):
    id: UUID
    skill_id: Optional[UUID] = None
    skill_level_id: Optional[UUID] = None
    criterion_key: Optional[str] = None
    sample_role: SampleRole
    file_format: str
    file_size_bytes: int
    participant_id: Optional[str] = None
    analysis_ready: bool
    analysis_notes: list[str] = Field(default_factory=list)
    created_at: datetime


class SkillLabModelResponse(BaseModel):
    id: UUID
    skill_id: Optional[UUID] = None
    version: str
    activa: bool
    metricas: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class SkillLabCategory(BaseModel):
    id: UUID
    name: str


class SkillLabChallengeType(BaseModel):
    id: UUID
    name: str
    code: str
    evaluation_modality: str


class SkillLabSkill(BaseModel):
    id: UUID
    name: str
    category: SkillLabCategory
    challenge_type: Optional[SkillLabChallengeType] = None
    min_approval_threshold: float


class SkillLabCriterion(BaseModel):
    key: str
    name: str
    weight: float
    description: str
    metric_type: str
    target: Optional[float] = None
    training_samples: int
    has_reference: bool


class SkillLabLevel(BaseModel):
    id: UUID
    level_number: int
    name: str
    min_score: float
    weights_total: float
    criteria: list[SkillLabCriterion] = Field(default_factory=list)
    training_samples: int
    reference: Optional[SkillLabSampleResponse] = None


class SkillLabReadiness(BaseModel):
    ready_to_validate: bool
    issues: list[str] = Field(default_factory=list)


class SkillLabConfigResponse(BaseModel):
    skill: SkillLabSkill
    levels: list[SkillLabLevel] = Field(default_factory=list)
    active_model: Optional[SkillLabModelResponse] = None
    readiness: SkillLabReadiness
