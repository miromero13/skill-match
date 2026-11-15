from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


CANONICAL_LEVELS = {
    1: "Principiante", 2: "Elemental", 3: "Intermedio",
    4: "Avanzado", 5: "Master Pedagogo",
}


class CategoryCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = None
    is_active: bool = True


class CategoryUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    slug: str
    description: Optional[str]
    is_active: bool


class CategoryListResponse(BaseModel):
    statuscode: int
    message: str
    data: list[CategoryResponse]
    count: int


class ChallengeTypeCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    code: str = Field(min_length=1, max_length=50)
    evaluation_modality: str = Field(min_length=1, max_length=50)
    description: Optional[str] = None
    is_active: bool = True


class ChallengeTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    code: str
    evaluation_modality: str
    description: Optional[str]
    is_active: bool


class ChallengeTypeListResponse(BaseModel):
    statuscode: int
    message: str
    data: list[ChallengeTypeResponse]
    count: int


class RubricCriterionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    weight: float = Field(ge=0)
    description: str


class RubricSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    instructions: Optional[str] = None
    min_score: float = Field(default=70.0, ge=0, le=100)
    criteria: list[RubricCriterionSchema] = Field(default_factory=list)


class SkillLevelSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    level_number: int = Field(ge=1, le=5)
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = None
    rubric: Optional[RubricSchema] = None


class SkillCreateRequest(BaseModel):
    category_id: UUID
    name: str = Field(min_length=1, max_length=150)
    challenge_type_id: Optional[UUID] = None
    description: Optional[str] = None
    min_approval_threshold: float = Field(default=80.0, ge=0, le=100)
    is_ready_to_publish: bool = False
    levels: Optional[list[SkillLevelSchema]] = None


class SkillUpdateRequest(BaseModel):
    category_id: UUID
    name: str = Field(min_length=1, max_length=150)
    challenge_type_id: Optional[UUID] = None
    description: Optional[str] = None
    min_approval_threshold: float = Field(default=80.0, ge=0, le=100)
    is_ready_to_publish: bool = False
    is_active: bool = False
    levels: Optional[list[SkillLevelSchema]] = None


class SkillResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    category_id: UUID
    challenge_type_id: Optional[UUID]
    name: str
    slug: str
    description: Optional[str]
    min_approval_threshold: float
    is_ready_to_publish: bool
    is_active: bool
    levels: list[SkillLevelSchema] = Field(default_factory=list)


class SkillListResponse(BaseModel):
    statuscode: int
    message: str
    data: list[SkillResponse]
    count: int


class ToggleRequest(BaseModel):
    is_ready_to_publish: bool


class StatusRequest(BaseModel):
    is_active: bool
