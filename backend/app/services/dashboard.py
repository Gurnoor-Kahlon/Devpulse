from datetime import timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.incident import Incident
from app.models.monitor import Monitor
from app.schemas.dashboard import (
    DashboardResponse,
    DashboardWindow,
    MonitorCounts,
)
from app.schemas.incidents import IncidentResponse
from app.services.analytics import get_run_history


def get_dashboard(db: Session, user_id: UUID, window: DashboardWindow) -> DashboardResponse:
    history = get_run_history(db, user_id, window)
    end = history.end
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
        **history.model_dump(),
        monitors=counts,
        open_incidents=open_count or 0,
        recent_incidents=[IncidentResponse.model_validate(row) for row in recent],
    )
