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


class SkillLabPreviewUrlResponse(BaseModel):
    """Short-lived playback URL (relative to the API origin, e.g. `/api/admin/skill-lab/samples/{id}/file?token=`)."""

    url: str
    expires_at: datetime
    content_type: Literal["video/mp4", "video/webm", "video/quicktime"]


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


# ---------------------------------------------------------------- Validation result (engine contract)


class ValidationCriterionResult(BaseModel):
    key: str
    name: str
    weight: float
    metric_type: str
    evaluable: bool
    score: Optional[float] = None  # null when the criterion is not evaluable
    detail: dict[str, Any] = Field(default_factory=dict)
    note: Optional[str] = None


class ValidationLevelResult(BaseModel):
    level_id: str
    level_number: int
    name: str
    min_score: float
    evaluable: bool
    score: Optional[float] = None  # null when the level is not evaluable
    passed: bool
    not_evaluable_reason: Optional[str] = None
    criteria: list[ValidationCriterionResult] = Field(default_factory=list)


class ValidationLevelRef(BaseModel):
    level_id: str
    level_number: int
    name: str


class ModelLevelEstimate(BaseModel):
    level_id: str
    name: str
    confidence: float


class SkillValidationResult(BaseModel):
    skill_id: str
    skill_name: str
    engine_version: str
    model_version: Optional[str] = None
    analysis_complete: bool
    target_level_id: Optional[str] = None
    achieved_level: Optional[ValidationLevelRef] = None
    score: float
    min_approval_threshold: float
    meets_skill_threshold: bool
    approved: bool
    model_level_estimate: Optional[ModelLevelEstimate] = None
    levels: list[ValidationLevelResult] = Field(default_factory=list)
    pose_detected_ratio: Optional[float] = None
    duration_seconds: Optional[float] = None
    notes: list[str] = Field(default_factory=list)
