from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="Mensaje del usuario al asistente")


class ChatActionPayload(BaseModel):
    type: str = Field(..., description="Tipo de acción: 'wallet_topup' | 'instructor_card' | 'sessions_list' | 'faq_info'")
    data: dict[str, Any] = Field(default_factory=dict, description="Datos asociados para componentes interactivos de UI")


class ChatMessageResponse(BaseModel):
    reply: str = Field(..., description="Texto de respuesta en Markdown generado por el asistente")
    action: ChatActionPayload | None = Field(default=None, description="Acción interactiva o tarjeta generativa opcional")
    suggested_prompts: list[str] = Field(default_factory=list, description="Píldoras de preguntas sugeridas")


class ChatHistoryItem(BaseModel):
    id: str
    role: str = Field(..., description="'user' | 'assistant'")
    content: str
    timestamp: datetime
    action: ChatActionPayload | None = None
