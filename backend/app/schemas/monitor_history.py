from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.schemas.assertions import AssertionResult
from app.schemas.dashboard import RunHistory
from app.schemas.monitors import MonitorResponse


class StatusCount(BaseModel):
    http_status: int
    count: int
    percentage: float


class MonitorAnalytics(RunHistory):
    monitor: MonitorResponse
    archived_at: datetime | None
    status_distribution: list[StatusCount]


class CheckEvidence(BaseModel):
    id: UUID
    run_id: UUID
    scheduled_at: datetime
    configuration_version: int
    trigger: Literal["manual", "scheduled"]
    run_state: Literal["pending", "running", "completed", "cancelled", "infrastructure_failed"]
    final_outcome: str | None
    attempt_number: int
    is_final_attempt: bool
    started_at: datetime
    finished_at: datetime
    outcome: Literal["success", "failure", "blocked", "infrastructure_failure"]
    http_status: int | None
    duration_ms: float
    error_code: str | None
    error_message: str | None
    assertion_results: list[AssertionResult] = []


class CheckPage(BaseModel):
    start: datetime
    end: datetime
    items: list[CheckEvidence]
    next_cursor: str | None
