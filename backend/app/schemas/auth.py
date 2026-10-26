from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field

class TokenRefreshRequest(BaseModel):
    """Payload para solicitud de rotación de tokens (POST /api/auth/refresh)."""
    refresh_token: str = Field(
        ...,
        description="Refresh Token JWT firmado emitido previamente",
        examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."]
    )

class TokenRefreshResponse(BaseModel):
    """Respuesta con el nuevo par de tokens tras rotación exitosa."""
    access_token: str = Field(..., description="Nuevo Access Token JWT con claim 'role'")
    refresh_token: str = Field(..., description="Nuevo Refresh Token JWT rotado")
    token_type: str = Field(default="bearer", description="Esquema de autenticación HTTP")
    expires_in: int = Field(..., description="Segundos hasta la expiración del Access Token")

class UserMeResponse(BaseModel):
    """Identidad, perfil y rol del usuario autenticado actual (GET /api/auth/me)."""
    id: UUID = Field(..., description="Identificador único del usuario")
    email: EmailStr = Field(..., description="Correo electrónico del usuario")
    full_name: str = Field(..., description="Nombre completo del usuario")
    role: str = Field(..., description="Rol canónico del usuario ('MEMBER' o 'ADMIN')")
    is_active: bool = Field(..., description="Estado de actividad de la cuenta")
    avatar_url: Optional[str] = Field(default=None, description="URL del avatar del perfil")
    phone_number: Optional[str] = Field(default=None, description="Número de teléfono (si aplica)")
    provider: Optional[str] = Field(default=None, description="Proveedor de autenticación de origen")

    class Config:
        from_attributes = True
