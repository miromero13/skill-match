from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field

class AdminLoginRequest(BaseModel):
    """Payload del formulario de login de administradores (POST /api/admin/auth/login)."""
    email: EmailStr = Field(
        ...,
        description="Correo electrónico institucional del administrador",
        examples=["admin.gonzalo@skillmatch.io"]
    )
    password: str = Field(
        ...,
        min_length=8,
        description="Contraseña cifrada del administrador",
        examples=["SuperSecretPassword123!"]
    )
    remember_me: bool = Field(
        default=False,
        description="Mantener sesión persistente en terminal de trabajo"
    )

class AdminUserResponse(BaseModel):
    """Datos públicos del perfil administrativo autenticado."""
    id: UUID
    email: EmailStr
    full_name: str
    role: str = "ADMIN"
    is_active: bool
    avatar_url: Optional[str] = None

    class Config:
        from_attributes = True

class AdminTokenData(BaseModel):
    """Sobre de respuesta con tokens JWT generados tras autenticación exitosa."""
    access_token: str = Field(..., description="Access Token JWT con claim 'role': 'ADMIN'")
    refresh_token: str = Field(..., description="Refresh Token JWT")
    token_type: str = Field(default="bearer", description="Esquema de autenticación HTTP")
    expires_in: int = Field(..., description="Segundos hasta la expiración del Access Token")
    user: AdminUserResponse
