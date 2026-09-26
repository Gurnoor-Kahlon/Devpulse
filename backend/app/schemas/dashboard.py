from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.incidents import IncidentResponse

DashboardWindow = Literal["24h", "7d", "30d"]


class RunMetrics(BaseModel):
    successful_runs: int
    failed_runs: int
    observations: int
    excluded_runs: int
    uptime_percent: float | None
    response_count: int
    mean_latency_ms: float | None
    first_observation_at: datetime | None
    last_observation_at: datetime | None


class TrendBucket(RunMetrics):
    start: datetime
    end: datetime
    partial: bool


class MonitorCounts(BaseModel):
    total: int = 0
    operational: int = 0
    down: int = 0
    confirming_failure: int = 0
    unknown: int = 0
    paused: int = 0
    stale: int = 0
    awaiting_check: int = 0


class DashboardResponse(BaseModel):
    window: DashboardWindow
    start: datetime
    end: datetime
    bucket_seconds: int
    metrics: RunMetrics
    buckets: list[TrendBucket]
    monitors: MonitorCounts
    open_incidents: int
    recent_incidents: list[IncidentResponse]
