from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, computed_field


class IncidentEvidence(BaseModel):
    attempt_number: int
    configuration_version: int
    method: Literal["GET", "HEAD"]
    expected_status: int
    started_at: datetime
    finished_at: datetime
    outcome: Literal["success", "failure"]
    http_status: int | None
    duration_ms: float
    error_code: str | None
    error_message: str | None


class IncidentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    monitor_id: UUID
    monitor_name: str
    started_at: datetime
    confirmed_at: datetime
    resolved_at: datetime | None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def status(self) -> Literal["open", "resolved"]:
        return "open" if self.resolved_at is None else "resolved"


class IncidentDetail(IncidentResponse):
    opening_run_id: UUID | None
    opening_check_id: UUID | None
    confirmation_check_id: UUID | None
    recovery_run_id: UUID | None
    recovery_check_id: UUID | None
    opening_evidence: IncidentEvidence
    confirmation_evidence: IncidentEvidence
    recovery_evidence: IncidentEvidence | None


class IncidentPage(BaseModel):
    items: list[IncidentResponse]
    next_cursor: str | None
