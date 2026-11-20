import hashlib
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator, model_validator


CANONICAL_LEVELS = {
    1: "Principiante", 2: "Elemental", 3: "Intermedio",
    4: "Avanzado", 5: "Master Pedagogo",
}


class NamedCatalogRequest(BaseModel):
    @field_validator("name", mode="before", check_fields=False)
    @classmethod
    def nonempty_name(cls, value):
        if not isinstance(value, str) or not value.strip():
            raise ValueError("El nombre no puede estar vacío.")
        return " ".join(value.split())


class CategoryCreateRequest(NamedCatalogRequest):
    parent_id: Optional[UUID] = None
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = None
    is_active: bool = True


class CategoryUpdateRequest(NamedCatalogRequest):
    parent_id: Optional[UUID] = None
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    parent_id: Optional[UUID] = None
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


METRIC_REFERENCE_REPLICATION = "REFERENCE_REPLICATION"
METRIC_BALL_TOUCH_STREAK = "BALL_TOUCH_STREAK"
CriterionMetricType = Literal["REFERENCE_REPLICATION", "BALL_TOUCH_STREAK"]
CRITERION_KEY_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"
WEIGHTS_TOTAL_TOLERANCE = 0.01


def criterion_name_key(name: str) -> str:
    return " ".join(str(name).split()).casefold()


def generated_criterion_key(index: int, name: str) -> str:
    """Deterministic short id for a criterion stored without `key` (same input, same key)."""
    return "c" + hashlib.sha1(f"{index}|{criterion_name_key(name)}".encode("utf-8")).hexdigest()[:10]


class RubricCriterionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    key: Optional[str] = Field(default=None, pattern=CRITERION_KEY_PATTERN)
    name: str
    weight: float = Field(ge=0)
    description: str
    metric_type: CriterionMetricType = METRIC_REFERENCE_REPLICATION
    target: Optional[float] = Field(default=None, gt=0)


class RubricSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    instructions: Optional[str] = None
    min_score: float = Field(default=70.0, ge=0, le=100)
    criteria: list[RubricCriterionSchema] = Field(default_factory=list)
    # Indexes whose key was generated here (not sent by the client nor stored).
    _generated_key_indexes: set[int] = PrivateAttr(default_factory=set)

    @model_validator(mode="after")
    def fill_missing_criterion_keys(self):
        # Provided keys are kept as-is; missing ones (new criteria or legacy stored rows)
        # get a deterministic key that never collides with another key of the level.
        used = {criterion.key for criterion in self.criteria if criterion.key}
        for index, criterion in enumerate(self.criteria):
            if criterion.key:
                continue
            self._generated_key_indexes.add(index)
            base = candidate = generated_criterion_key(index, criterion.name)
            suffix = 2
            while candidate in used:
                candidate = f"{base}-{suffix}"
                suffix += 1
            criterion.key = candidate
            used.add(candidate)
        return self

    @property
    def weights_total(self) -> float:
        return sum(criterion.weight for criterion in self.criteria)

    def reuse_keys_by_name(self, stored: list["RubricCriterionSchema"]) -> None:
        """For criteria sent without key, reuse the stored key of the criterion with the same name."""
        stored_keys: dict[str, str] = {}
        for criterion in stored:
            stored_keys.setdefault(criterion_name_key(criterion.name), criterion.key)
        used = {c.key for index, c in enumerate(self.criteria) if index not in self._generated_key_indexes}
        for index in sorted(self._generated_key_indexes):
            criterion = self.criteria[index]
            reusable = stored_keys.get(criterion_name_key(criterion.name))
            if reusable and reusable not in used:
                criterion.key = reusable
            used.add(criterion.key)


class SkillLevelSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    level_number: int = Field(ge=1, le=5)
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = None
    rubric: Optional[RubricSchema] = None


class SkillCreateRequest(NamedCatalogRequest):
    category_id: UUID
    name: str = Field(min_length=1, max_length=150)
    challenge_type_id: Optional[UUID] = None
    description: Optional[str] = None
    min_approval_threshold: float = Field(default=80.0, ge=0, le=100)
    is_ready_to_publish: bool = False
    levels: Optional[list[SkillLevelSchema]] = None


class SkillUpdateRequest(NamedCatalogRequest):
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
