from uuid import UUID

from pydantic import (
    AwareDatetime, BaseModel, ConfigDict, Field, StrictBool,
    field_validator, model_validator,
)

from app.models.notification import NOTIFICATION_CATEGORIES, NotificationCategory, NotificationType


class NotificationEmission(BaseModel):
    """Internal domain input, never a public notification-creation request."""

    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    event_id: UUID
    notification_type: NotificationType
    title: str = Field(strict=True, min_length=1, max_length=150)
    message: str = Field(strict=True, min_length=1, max_length=2000)

    @field_validator("title", "message", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class NotificationChannels(BaseModel):
    model_config = ConfigDict(extra="forbid")

    in_app: StrictBool
    push: StrictBool
    email: StrictBool


class NotificationCategories(BaseModel):
    model_config = ConfigDict(extra="forbid")

    INTERCHANGES: StrictBool
    POINTS: StrictBool
    GENERAL: StrictBool


class NotificationPreferencesWrite(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={
        "example": {
            "revision": 0,
            "channels": {"in_app": True, "push": False, "email": False},
            "categories": {"INTERCHANGES": True, "POINTS": True, "GENERAL": True},
        },
    })

    revision: int = Field(strict=True, ge=0)
    channels: NotificationChannels
    categories: NotificationCategories


class NotificationPreferencesResponse(NotificationPreferencesWrite):
    @classmethod
    def defaults(cls) -> "NotificationPreferencesResponse":
        # New nested values on each call; GET need not materialize a database row.
        return cls(
            revision=0,
            channels=NotificationChannels(in_app=True, push=False, email=False),
            categories=NotificationCategories(INTERCHANGES=True, POINTS=True, GENERAL=True),
        )


class NotificationFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    unread: bool | None = None
    category: NotificationCategory | None = None

    @field_validator("page", "page_size", mode="before")
    @classmethod
    def reject_boolean_pagination(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("La paginación requiere un número entero.")
        return value


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    type: NotificationType
    category: NotificationCategory
    title: str
    message: str
    created_at: AwareDatetime
    read_at: AwareDatetime | None

    @model_validator(mode="before")
    @classmethod
    def reject_deleted_record(cls, value: object) -> object:
        if getattr(value, "deleted_at", None) is not None:
            raise ValueError("Una notificación eliminada no se puede publicar.")
        return value

    @model_validator(mode="after")
    def consistent_category(self) -> "NotificationResponse":
        if NOTIFICATION_CATEGORIES[self.type] != self.category:
            raise ValueError("La categoría no corresponde al tipo de notificación.")
        return self
