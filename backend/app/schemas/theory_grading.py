"""Strict provider output contract; final scores are computed by the server."""
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, field_validator


class CriterionGrade(BaseModel):
    model_config = ConfigDict(extra="forbid")
    criterion: str = Field(min_length=1, max_length=120)
    attainment: FiniteFloat = Field(ge=0, le=1)
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("attainment", mode="before")
    @classmethod
    def numeric_not_boolean_or_string(cls, value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("attainment must be numeric")
        return value


class ProviderGrade(BaseModel):
    model_config = ConfigDict(extra="forbid")
    criteria: list[CriterionGrade] = Field(min_length=1, max_length=20)
    feedback: str = Field(min_length=1, max_length=2000)

    def validate_criteria(self, expected: set[str]) -> "ProviderGrade":
        actual = [item.criterion for item in self.criteria]
        if set(actual) != expected or len(actual) != len(set(actual)):
            raise ValueError("Provider criteria do not match the rubric")
        return self
