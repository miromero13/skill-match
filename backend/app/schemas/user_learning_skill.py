import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.user_learning_skill import UrgencyLevel


class SkillSummary(BaseModel):
    """Resumen de habilidad asociada a una demanda de aprendizaje."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    category_id: uuid.UUID
    category_name: Optional[str] = None


class UserLearningSkillCreate(BaseModel):
    """Contrato de entrada para registrar una habilidad a aprender (HU-15)."""
    skill_id: uuid.UUID = Field(..., description="ID de la habilidad del catálogo")
    current_level: int = Field(default=1, ge=1, le=5, description="Nivel actual o de partida (1-5)")
    target_level: int = Field(default=3, ge=1, le=5, description="Nivel meta u objetivo deseado (1-5)")
    urgency: UrgencyLevel = Field(default=UrgencyLevel.MEDIUM, description="Urgencia de aprendizaje (LOW, MEDIUM, HIGH)")
    notes: Optional[str] = Field(default=None, max_length=500, description="Notas u objetivos personales")

    @model_validator(mode="after")
    def validate_levels(self) -> "UserLearningSkillCreate":
        if self.target_level < self.current_level:
            raise ValueError("El nivel meta (target_level) debe ser mayor o igual al nivel actual (current_level).")
        return self


class UserLearningSkillUpdate(BaseModel):
    """Contrato de entrada para actualizar una demanda de aprendizaje existente (HU-15)."""
    current_level: Optional[int] = Field(default=None, ge=1, le=5, description="Nivel actual (1-5)")
    target_level: Optional[int] = Field(default=None, ge=1, le=5, description="Nivel meta (1-5)")
    urgency: Optional[UrgencyLevel] = Field(default=None, description="Urgencia (LOW, MEDIUM, HIGH)")
    notes: Optional[str] = Field(default=None, max_length=500, description="Notas u objetivos personales")

    @model_validator(mode="after")
    def validate_levels(self) -> "UserLearningSkillUpdate":
        if self.current_level is not None and self.target_level is not None:
            if self.target_level < self.current_level:
                raise ValueError("El nivel meta (target_level) debe ser mayor o igual al nivel actual (current_level).")
        return self


class UserLearningSkillResponse(BaseModel):
    """Contrato de salida para una habilidad que el miembro desea aprender."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    skill_id: uuid.UUID
    current_level: int
    target_level: int
    urgency: UrgencyLevel
    notes: Optional[str] = None
    skill: Optional[SkillSummary] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
