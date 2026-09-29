from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.dashboard import RunHistory


class DemoIncident(BaseModel):
    started_at: datetime
    confirmed_at: datetime
    resolved_at: datetime | None


class DemoMonitor(BaseModel):
    slug: str
    label: str
    controlled_failure: bool
    state: Literal["operational", "down", "confirming_failure", "unknown", "paused"]
    stale: bool
    last_checked_at: datetime | None
    history: RunHistory
    recent_incidents: list[DemoIncident]


class DemoResponse(BaseModel):
    generated_at: datetime
    monitors: list[DemoMonitor]
