"""Admin diagnostics for native push (FCM). Never carries full tokens or credential content."""
from uuid import UUID

from pydantic import BaseModel, Field


class FirebaseStatus(BaseModel):
    initialized: bool
    source: str | None = Field(default=None, description="json | path | null")
    error: str | None = Field(default=None, description="Mensaje breve; nunca contiene material de la clave")


class PushDeviceCounts(BaseModel):
    active: int
    total: int
    users_with_active: int


class PushStatusResponse(BaseModel):
    firebase: FirebaseStatus
    devices: PushDeviceCounts


class PushTestRequest(BaseModel):
    user_id: UUID | None = Field(default=None, description="Destinatario; sin él se usan los 5 dispositivos activos más recientes")
    title: str | None = Field(default=None, min_length=1, max_length=150)
    body: str | None = Field(default=None, min_length=1, max_length=500)


class PushTestResult(BaseModel):
    user_id: UUID
    token_suffix: str = Field(description="Últimos 8 caracteres del token FCM")
    ok: bool
    error: str | None = None


class PushTestResponse(BaseModel):
    sent: int
    failed: int
    results: list[PushTestResult]
