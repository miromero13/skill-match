"""Strict HTTP and WebSocket contracts for HU-24 realtime notifications."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.notification import NotificationType
from app.schemas.notification import NotificationResponse


RealtimeNotificationType = Literal[
    NotificationType.MATCH_RECEIVED,
    NotificationType.MATCH_CONFIRMED,
    NotificationType.SESSION_PROPOSED,
    NotificationType.POINTS_RECEIVED,
]


class WebSocketTicketResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket: str = Field(strict=True, min_length=1)
    expires_in: int = Field(strict=True, ge=5, le=120)
    websocket_path: Literal["/ws/notifications"] = "/ws/notifications"


class RealtimeNotificationData(NotificationResponse):
    type: RealtimeNotificationType


class RealtimeNotificationEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: Literal["notification.created"]
    message: str = Field(strict=True, min_length=1, max_length=2000)
    data: RealtimeNotificationData

    @model_validator(mode="after")
    def message_matches_notification(self) -> "RealtimeNotificationEvent":
        if self.message != self.data.message:
            raise ValueError("El mensaje del evento no coincide con la notificación.")
        return self


class WebSocketClientMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: Literal["ping"]


class WebSocketPongMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: Literal["pong"] = "pong"
