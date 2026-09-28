"""Incident transitions run inside the fenced check-completion transaction."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.check import Check, CheckRun
from app.models.incident import Incident
from app.models.monitor import Monitor
from app.notifications.outbox import enqueue_transition


def evidence(check: Check, run: CheckRun, monitor: Monitor) -> dict[str, object]:
    # Fixed fields plus configured expectations; never retain actual response data.
    return {
        "attempt_number": check.attempt_number,
        "configuration_version": run.configuration_version,
        "method": monitor.method,
        "expected_status": monitor.expected_status,
        "started_at": check.started_at.isoformat(),
        "finished_at": check.finished_at.isoformat(),
        "outcome": check.outcome,
        "http_status": check.http_status,
        "duration_ms": check.duration_ms,
        "error_code": check.error_code,
        "error_message": check.error_message,
        "assertion_results": check.assertion_results,
    }


def apply_observation(db: Session, monitor: Monitor, run: CheckRun, check: Check) -> None:
    # The caller holds the monitor lock, serializing open/recovery transitions.
    incident = db.scalar(
        select(Incident).where(Incident.monitor_id == monitor.id, Incident.resolved_at.is_(None))
    )
    if check.outcome == "success":
        monitor.current_state = "operational"
        if incident is not None:
            incident.resolved_at = max(incident.confirmed_at, check.finished_at)
            incident.recovery_run_id, incident.recovery_check_id = run.id, check.id
            incident.recovery_evidence = evidence(check, run, monitor)
            enqueue_transition(db, monitor, incident, "resolved")
    elif check.outcome == "failure":
        if run.attempt_count < 3:
            monitor.current_state = "down" if incident else "confirming_failure"
        else:
            monitor.current_state = "down"
            if incident is None:
                first = db.scalar(
                    select(Check).where(Check.run_id == run.id, Check.attempt_number == 1)
                )
                assert first is not None
                incident = Incident(
                    monitor_id=monitor.id,
                    monitor_name=monitor.name,
                    started_at=first.started_at,
                    confirmed_at=max(first.started_at, check.finished_at),
                    opening_run_id=run.id,
                    opening_check_id=first.id,
                    confirmation_check_id=check.id,
                    opening_evidence=evidence(first, run, monitor),
                    confirmation_evidence=evidence(check, run, monitor),
                )
                db.add(incident)
                enqueue_transition(db, monitor, incident, "opened")
    elif monitor.current_state == "confirming_failure":
        monitor.current_state = "down" if incident else "unknown"
