from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.core.security import now_utc
from app.models.check import Check, CheckRun
from app.models.incident import Incident
from app.models.monitor import Monitor
from app.schemas.dashboard import (
    DashboardResponse,
    DashboardWindow,
    MonitorCounts,
    RunMetrics,
    TrendBucket,
)
from app.schemas.incidents import IncidentResponse

WINDOWS = {
    "24h": (timedelta(days=1), 3600),
    "7d": (timedelta(days=7), 21600),
    "30d": (timedelta(days=30), 86400),
}


def metrics(
    success: int = 0,
    failed: int = 0,
    excluded: int = 0,
    responses: int = 0,
    duration: float = 0,
    first: datetime | None = None,
    last: datetime | None = None,
) -> RunMetrics:
    count = success + failed
    return RunMetrics(
        successful_runs=success,
        failed_runs=failed,
        observations=count,
        excluded_runs=excluded,
        uptime_percent=100 * success / count if count else None,
        response_count=responses,
        mean_latency_ms=duration / responses if responses else None,
        first_observation_at=first,
        last_observation_at=last,
    )


def get_dashboard(db: Session, user_id: UUID, window: DashboardWindow) -> DashboardResponse:
    end = now_utc()
    duration, seconds = WINDOWS[window]
    start = end - duration
    eligible = func.coalesce(
        and_(
            CheckRun.state == "completed",
            CheckRun.final_outcome.in_(("success", "failure")),
            CheckRun.completed_at <= end,
        ),
        False,
    )
    responded = and_(eligible, Check.http_status.is_not(None))
    bucket = func.date_bin(
        timedelta(seconds=seconds), CheckRun.scheduled_at, datetime(1970, 1, 1, tzinfo=UTC)
    )
    # Exactly one final attempt may join each run. Missing raw checks never erase run outcomes.
    rows = (
        db.execute(
            select(
                bucket.label("bucket"),
                func.count()
                .filter(and_(eligible, CheckRun.final_outcome == "success"))
                .label("success"),
                func.count()
                .filter(and_(eligible, CheckRun.final_outcome == "failure"))
                .label("failed"),
                func.count().filter(~eligible).label("excluded"),
                func.count().filter(responded).label("responses"),
                func.coalesce(func.sum(Check.duration_ms).filter(responded), 0).label("duration"),
                func.min(CheckRun.scheduled_at).filter(eligible).label("first"),
                func.max(CheckRun.scheduled_at).filter(eligible).label("last"),
            )
            .select_from(CheckRun)
            .join(Monitor, Monitor.id == CheckRun.monitor_id)
            .outerjoin(
                Check,
                and_(Check.run_id == CheckRun.id, Check.attempt_number == CheckRun.attempt_count),
            )
            .where(
                Monitor.user_id == user_id,
                CheckRun.trigger == "scheduled",
                CheckRun.scheduled_at >= start,
                CheckRun.scheduled_at < end,
            )
            .group_by(bucket)
        )
        .mappings()
        .all()
    )
    indexed = {row["bucket"]: row for row in rows}
    buckets = []
    current = datetime.fromtimestamp(int(start.timestamp()) // seconds * seconds, UTC)
    while current < end:
        row = indexed.get(current)
        value = (
            metrics(
                row["success"],
                row["failed"],
                row["excluded"],
                row["responses"],
                row["duration"],
                row["first"],
                row["last"],
            )
            if row
            else metrics()
        )
        stop = current + timedelta(seconds=seconds)
        buckets.append(
            TrendBucket(
                **value.model_dump(),
                start=max(start, current),
                end=min(end, stop),
                partial=current < start or stop > end,
            )
        )
        current = stop
    firsts = [row["first"] for row in rows if row["first"] is not None]
    lasts = [row["last"] for row in rows if row["last"] is not None]
    totals = metrics(
        success=sum(row["success"] for row in rows),
        failed=sum(row["failed"] for row in rows),
        excluded=sum(row["excluded"] for row in rows),
        responses=sum(row["responses"] for row in rows),
        duration=sum(row["duration"] for row in rows),
        first=min(firsts) if firsts else None,
        last=max(lasts) if lasts else None,
    )
    # The account quota bounds this current-state projection to ten active monitors.
    counts = MonitorCounts()
    for monitor in db.execute(
        select(
            Monitor.enabled,
            Monitor.current_state,
            Monitor.last_scheduled_check_at,
            Monitor.updated_at,
            Monitor.interval_seconds,
        ).where(Monitor.user_id == user_id, Monitor.deleted_at.is_(None))
    ):
        counts.total += 1
        state = monitor.current_state if monitor.enabled else "paused"
        setattr(counts, state, getattr(counts, state) + 1)
        if monitor.enabled:
            baseline = monitor.last_scheduled_check_at or monitor.updated_at
            if end >= baseline + timedelta(seconds=2 * monitor.interval_seconds):
                counts.stale += 1
            elif monitor.last_scheduled_check_at is None:
                counts.awaiting_check += 1
    incident_query = (
        select(Incident)
        .join(Monitor, Monitor.id == Incident.monitor_id)
        .where(Monitor.user_id == user_id)
    )
    # Current incidents are independent of the analytics window and survive raw-history pruning.
    open_count = db.scalar(
        select(func.count()).select_from(
            incident_query.where(Incident.resolved_at.is_(None)).subquery()
        )
    )
    recent = db.scalars(
        incident_query.order_by(Incident.started_at.desc(), Incident.id.desc()).limit(5)
    )
    return DashboardResponse(
        window=window,
        start=start,
        end=end,
        bucket_seconds=seconds,
        metrics=totals,
        buckets=buckets,
        monitors=counts,
        open_incidents=open_count or 0,
        recent_incidents=[IncidentResponse.model_validate(row) for row in recent],
    )
