import re
import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, field_validator
from app.models.user import UserRole

class AdminCreateRequest(BaseModel):
    """Contrato de entrada para la creación de un nuevo administrador (RF-USR-10)."""
    email: EmailStr = Field(
        ...,
        description="Correo electrónico institucional único para el nuevo administrador",
        examples=["admin.nuevo@skillmatch.io"]
    )
    full_name: str = Field(
        ...,
        min_length=2,
        max_length=150,
        description="Nombre y apellido completo del administrador",
        examples=["Ing. Gonzalo Martínez"]
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Contraseña inicial robusta (al menos 8 caracteres, 1 mayúscula, 1 minúscula, 1 número y 1 carácter especial)"
    )

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres.")
        if not re.search(r"[A-Z]", value):
            raise ValueError("La contraseña debe contener al menos una letra mayúscula.")
        if not re.search(r"[a-z]", value):
            raise ValueError("La contraseña debe contener al menos una letra minúscula.")
        if not re.search(r"\d", value):
            raise ValueError("La contraseña debe contener al menos un número.")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>\-_=+\\/\[\]]", value):
            raise ValueError("La contraseña debe contener al esté al menos un carácter especial.")
        return value

class AdminStatusUpdateRequest(BaseModel):
    """Contrato para suspender o reactivar una cuenta administrativa (RF-USR-15)."""
    is_active: bool = Field(
        ...,
        description="Nuevo estado de activación de la cuenta (True = reactivada, False = suspendida)"
    )
    reason: Optional[str] = Field(
        None,
        max_length=255,
        description="Motivo administrativo o de seguridad para el registro de auditoría",
        examples=["Auditoría de seguridad preventiva"]
    )

class AdminItemResponse(BaseModel):
    """Contrato de lectura para un usuario administrador."""
    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole = UserRole.ADMIN
    is_active: bool
    is_locked: bool
    avatar_url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class AdminListResponse(BaseModel):
    """Sobre de respuesta estándar con conteo para listado administrativo."""
    statuscode: int = 200
    message: str = "Listado de administradores recuperado exitosamente"
    data: List[AdminItemResponse]
    count: int
