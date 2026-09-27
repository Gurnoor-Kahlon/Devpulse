import base64
import binascii
from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, func, select, tuple_
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.security import now_utc
from app.models.check import Check, CheckRun
from app.models.monitor import Monitor
from app.monitoring.executor import ERROR_MESSAGES
from app.schemas.dashboard import DashboardWindow
from app.schemas.monitor_history import CheckEvidence, CheckPage, MonitorAnalytics, StatusCount
from app.schemas.monitors import MonitorResponse
from app.services.analytics import WINDOWS, get_run_history


def owned_history(db: Session, user_id: UUID, monitor_id: UUID) -> Monitor:
    # Archive hides configurations from CRUD, but keeps owned history readable.
    monitor = db.scalar(select(Monitor).where(Monitor.id == monitor_id, Monitor.user_id == user_id))
    if monitor is None:
        raise ApiError(404, "monitor_not_found", "Monitor not found.")
    return monitor


def get_analytics(
    db: Session, user_id: UUID, monitor_id: UUID, window: DashboardWindow
) -> MonitorAnalytics:
    monitor = owned_history(db, user_id, monitor_id)
    history = get_run_history(db, user_id, window, monitor_id)
    rows = db.execute(
        select(Check.http_status, func.count().label("responses"))
        .select_from(CheckRun)
        .join(
            Check, and_(Check.run_id == CheckRun.id, Check.attempt_number == CheckRun.attempt_count)
        )
        .where(
            CheckRun.monitor_id == monitor.id,
            CheckRun.trigger == "scheduled",
            CheckRun.state == "completed",
            CheckRun.final_outcome.in_(("success", "failure")),
            CheckRun.completed_at <= history.end,
            CheckRun.scheduled_at >= history.start,
            CheckRun.scheduled_at < history.end,
            Check.http_status.is_not(None),
        )
        .group_by(Check.http_status)
        .order_by(Check.http_status)
    ).all()
    total = sum(row.responses for row in rows)
    return MonitorAnalytics(
        **history.model_dump(),
        monitor=MonitorResponse.model_validate(monitor),
        archived_at=monitor.deleted_at,
        status_distribution=[
            StatusCount(
                http_status=row.http_status,
                count=row.responses,
                percentage=100 * row.responses / total,
            )
            for row in rows
        ],
    )


def decode_cursor(
    value: str, monitor_id: UUID, window: DashboardWindow
) -> tuple[datetime, datetime, datetime, UUID, int]:
    try:
        raw = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
        scope, selected, start_raw, end_raw, scheduled_raw, run_raw, attempt_raw = raw.decode(
            "ascii"
        ).split("|")
        start, end, scheduled = (
            datetime.fromisoformat(v) for v in (start_raw, end_raw, scheduled_raw)
        )
        if (
            scope != str(monitor_id)
            or selected != window
            or any(v.utcoffset() is None for v in (start, end, scheduled))
            or end - start != WINDOWS[window][0]
            or not start <= scheduled < end
            or end > now_utc()
            or not 1 <= int(attempt_raw) <= 3
        ):
            raise ValueError
        return start, end, scheduled, UUID(run_raw), int(attempt_raw)
    except (ValueError, UnicodeError, binascii.Error, OverflowError):
        raise ApiError(
            422, "invalid_cursor", "Use a cursor returned by this monitor's check history."
        ) from None


def list_checks(
    db: Session,
    user_id: UUID,
    monitor_id: UUID,
    window: DashboardWindow,
    limit: int,
    cursor: str | None,
) -> CheckPage:
    owned_history(db, user_id, monitor_id)
    end = now_utc()
    start = end - WINDOWS[window][0]
    after = None
    if cursor is not None:
        start, end, scheduled, run_id, attempt = decode_cursor(cursor, monitor_id, window)
        after = (scheduled, run_id, attempt)
    query = (
        select(Check, CheckRun)
        .join(CheckRun, CheckRun.id == Check.run_id)
        .where(
            CheckRun.monitor_id == monitor_id,
            CheckRun.scheduled_at >= start,
            CheckRun.scheduled_at < end,
            Check.finished_at <= end,
        )
    )
    if after is not None:
        query = query.where(
            tuple_(CheckRun.scheduled_at, CheckRun.id, Check.attempt_number) < after
        )
    rows = db.execute(
        query.order_by(
            CheckRun.scheduled_at.desc(), CheckRun.id.desc(), Check.attempt_number.desc()
        ).limit(limit + 1)
    ).all()
    page = rows[:limit]
    next_cursor = None
    if len(rows) > limit:
        last_check, last_run = page[-1]
        raw = "|".join(
            (
                str(monitor_id),
                window,
                start.isoformat(),
                end.isoformat(),
                last_run.scheduled_at.isoformat(),
                str(last_run.id),
                str(last_check.attempt_number),
            )
        )
        next_cursor = base64.urlsafe_b64encode(raw.encode("ascii")).decode("ascii").rstrip("=")
    items = []
    for check, run in page:
        # Expose only the fixed vocabulary, never a stored/raw exception string.
        code = check.error_code if check.error_code in ERROR_MESSAGES else None
        items.append(
            CheckEvidence(
                id=check.id,
                run_id=run.id,
                scheduled_at=run.scheduled_at,
                configuration_version=run.configuration_version,
                trigger=run.trigger,
                run_state=run.state,
                final_outcome=run.final_outcome,
                attempt_number=check.attempt_number,
                is_final_attempt=run.state not in ("pending", "running")
                and check.attempt_number == run.attempt_count,
                started_at=check.started_at,
                finished_at=check.finished_at,
                outcome=check.outcome,
                http_status=check.http_status,
                duration_ms=check.duration_ms,
                error_code=code,
                error_message=ERROR_MESSAGES[code] if code else None,
            )
        )
    return CheckPage(start=start, end=end, items=items, next_cursor=next_cursor)
