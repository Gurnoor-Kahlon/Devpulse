from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import now_utc
from app.models.auth import User
from app.models.incident import Incident
from app.models.monitor import Monitor
from app.schemas.dashboard import DashboardWindow
from app.schemas.demo import DemoIncident, DemoMonitor, DemoResponse
from app.services.analytics import get_run_history


def get_demo(db: Session, settings: Settings, window: DashboardWindow) -> DemoResponse:
    result = DemoResponse(generated_at=now_utc(), monitors=[])
    for publication in settings.demo_publications:
        # Project only necessary columns; private names, URLs and evidence never enter this view.
        monitor = db.execute(
            select(
                Monitor.enabled,
                Monitor.current_state,
                Monitor.last_scheduled_check_at,
                Monitor.updated_at,
                Monitor.interval_seconds,
            )
            .join(User, User.id == Monitor.user_id)
            .where(
                Monitor.id == publication.monitor_id,
                Monitor.user_id == publication.owner_id,
                Monitor.configuration_version == publication.configuration_version,
                Monitor.deleted_at.is_(None),
                User.email_verified_at.is_not(None),
            )
        ).one_or_none()
        if monitor is None:
            continue
        history = get_run_history(db, publication.owner_id, window, publication.monitor_id)
        incidents = db.execute(
            select(Incident.started_at, Incident.confirmed_at, Incident.resolved_at)
            .where(Incident.monitor_id == publication.monitor_id)
            .order_by(Incident.started_at.desc(), Incident.id.desc())
            .limit(5)
        )
        result.monitors.append(
            DemoMonitor(
                slug=publication.slug,
                label=publication.label,
                controlled_failure=publication.controlled_failure,
                state=monitor.current_state if monitor.enabled else "paused",
                stale=bool(
                    monitor.enabled
                    and result.generated_at
                    >= (monitor.last_scheduled_check_at or monitor.updated_at)
                    + timedelta(seconds=2 * monitor.interval_seconds)
                ),
                last_checked_at=monitor.last_scheduled_check_at,
                history=history,
                recent_incidents=[DemoIncident(**row._mapping) for row in incidents],
            )
        )
    return result
