import re
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator, model_validator

TIME_REGEX = re.compile(r"^([01]\d|2[0-3]):(00|30)$")
ALLOWED_MODALITIES = {"VIRTUAL", "PRESENCIAL", "BOTH"}


class AvailabilitySlotInput(BaseModel):
    """Franja horaria de 30 min o bloque múltiplo de 30 min dentro de la matriz semanal."""
    day_of_week: int = Field(..., ge=0, le=6, description="0=Lunes .. 6=Domingo")
    start_time: str = Field(..., description="Formato HH:MM en intervalos de 30 min")
    end_time: str = Field(..., description="Formato HH:MM en intervalos de 30 min")
    is_enabled: bool = Field(default=True)
    modality: str = Field(default="BOTH")

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        val = v.strip()
        if not TIME_REGEX.match(val):
            raise ValueError("El horario debe estar en formato HH:MM en bloques de 30 minutos (ej. 08:00, 08:30).")
        return val

    @field_validator("modality")
    @classmethod
    def validate_modality(cls, v: str) -> str:
        val = v.strip().upper()
        if val not in ALLOWED_MODALITIES:
            raise ValueError(f"La modalidad debe ser una de {sorted(ALLOWED_MODALITIES)}.")
        return val

    @model_validator(mode="after")
    def validate_time_order(self) -> "AvailabilitySlotInput":
        if self.end_time <= self.start_time:
            raise ValueError("La hora de fin (end_time) debe ser estrictamente posterior a la hora de inicio (start_time).")
        return self


class AvailabilityMatrixUpdate(BaseModel):
    """Payload para reemplazar la matriz de disponibilidad semanal completa (PUT /api/users/me/availability)."""
    slots: list[AvailabilitySlotInput] = Field(default_factory=list)
    timezone: Optional[str] = Field(default=None, min_length=2, max_length=100)
    buffer_minutes: Optional[int] = Field(default=None)

    @model_validator(mode="after")
    def validate_no_overlapping_slots(self) -> "AvailabilityMatrixUpdate":
        by_day: dict[int, list[tuple[str, str]]] = {}
        for slot in self.slots:
            if not slot.is_enabled:
                continue
            day_ranges = by_day.setdefault(slot.day_of_week, [])
            for existing_start, existing_end in day_ranges:
                if not (slot.end_time <= existing_start or slot.start_time >= existing_end):
                    raise ValueError(
                        f"Solapamiento detectado en el día {slot.day_of_week} entre "
                        f"{slot.start_time}-{slot.end_time} y {existing_start}-{existing_end}."
                    )
            day_ranges.append((slot.start_time, slot.end_time))
        return self


class AvailabilitySlotResponse(BaseModel):
    """Respuesta de una franja horaria de disponibilidad semanal."""
    id: UUID
    user_id: UUID
    day_of_week: int
    start_time: str
    end_time: str
    is_enabled: bool
    modality: str = "BOTH"

    model_config = {"from_attributes": True}
