from datetime import datetime
from typing import Annotated, Literal, Self
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StrictBool,
    StringConstraints,
    model_validator,
)


def normalize_url(value: str) -> str:
    # Syntax only. Connection-time destination validation belongs to the probe executor.
    if not value.lower().startswith(("http://", "https://")):
        raise ValueError("Invalid monitor URL")
    authority = urlsplit(value)
    if not authority.netloc or authority.username is not None:
        raise ValueError("Invalid monitor URL")
    if any(ord(char) <= 32 or ord(char) == 127 for char in value) or "\\" in value or "#" in value:
        raise ValueError("Invalid monitor URL")
    parsed = HttpUrl(value)
    if parsed.username is not None or parsed.password is not None or parsed.port not in (80, 443):
        raise ValueError("Invalid monitor URL")
    normalized = str(parsed)
    if len(normalized) > 2048:
        raise ValueError("Invalid monitor URL")
    return normalized


Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
MonitorUrl = Annotated[str, Field(min_length=1, max_length=2048), AfterValidator(normalize_url)]
Method = Literal["GET", "HEAD"]
ExpectedStatus = Annotated[int, Field(strict=True, ge=200, le=599)]
Interval = Annotated[int, Field(strict=True, ge=60, le=86400)]
Timeout = Annotated[int, Field(strict=True, ge=1, le=10)]
Version = Annotated[int, Field(strict=True, ge=1, le=2147483647)]


class MonitorCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    url: MonitorUrl
    method: Method = "GET"
    expected_status: ExpectedStatus = 200
    interval_seconds: Interval = 60
    timeout_seconds: Timeout = 5
    enabled: StrictBool = True


class MonitorUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    configuration_version: Version
    name: Name | None = None
    url: MonitorUrl | None = None
    method: Method | None = None
    expected_status: ExpectedStatus | None = None
    interval_seconds: Interval | None = None
    timeout_seconds: Timeout | None = None
    enabled: StrictBool | None = None

    @model_validator(mode="after")
    def require_changes(self) -> Self:
        if self.model_fields_set == {"configuration_version"}:
            raise ValueError("Supply at least one setting")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Settings cannot be null")
        return self


class MonitorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    url: str
    method: Method
    expected_status: int
    interval_seconds: int
    timeout_seconds: int
    enabled: bool
    configuration_version: int
    next_due_at: datetime | None
    current_state: Literal["unknown", "operational", "down", "confirming_failure"]
    last_completed_check_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MonitorPage(BaseModel):
    items: list[MonitorResponse]
    next_cursor: str | None
