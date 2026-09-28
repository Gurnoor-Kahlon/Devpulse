from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool


class NotificationPreferences(BaseModel):
    configuration_version: int
    enabled: bool
    on_open: bool
    on_recovery: bool
    destination: str
    verified: bool


class NotificationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    configuration_version: Annotated[int, Field(strict=True, ge=0, le=2147483646)]
    enabled: StrictBool
    on_open: StrictBool
    on_recovery: StrictBool


class DeliveryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    incident_id: UUID
    transition: Literal["opened", "resolved"]
    status: Literal["pending", "sending", "sent", "failed", "cancelled"]
    cancel_requested: bool
    attempt_count: int
    created_at: datetime
    next_attempt_at: datetime | None
    completed_at: datetime | None
    last_error_code: (
        Literal[
            "smtp_unavailable",
            "smtp_rejected",
            "delivery_unknown",
            "preferences_disabled",
            "email_unverified",
        ]
        | None
    )


class DeliveryPage(BaseModel):
    items: list[DeliveryResponse]
    next_cursor: str | None
