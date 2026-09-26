import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.logging import logger
from app.core.security import now_utc
from app.models.auth import User
from app.models.check import Check, CheckRun
from app.models.monitor import Monitor
from app.monitoring.executor import ERROR_MESSAGES, ProbeResult, execute_probe


class RunError(Exception):
    pass


@dataclass(frozen=True)
class ProbeSpec:
    run_id: UUID
    monitor_id: UUID
    configuration_version: int
    url: str
    method: str
    expected_status: int
    timeout_seconds: int
    lease_token: UUID


LEASE_SECONDS = 60


def create_pending_run(engine: Engine, monitor_id: UUID) -> UUID:
    with Session(engine) as db, db.begin():
        monitor = db.scalar(select(Monitor).where(Monitor.id == monitor_id).with_for_update())
        if monitor is None or not monitor.enabled or monitor.deleted_at is not None:
            raise RunError("Monitor is unavailable or paused.")
        user = db.get(User, monitor.user_id)
        if user is None or user.email_verified_at is None:
            raise RunError("The monitor owner must verify their email.")
        if db.scalar(
            select(CheckRun.id).where(
                CheckRun.monitor_id == monitor_id, CheckRun.state.in_(("pending", "running"))
            )
        ):
            raise RunError("A run is already active for this monitor.")
        run = CheckRun(
            monitor_id=monitor_id,
            scheduled_at=now_utc(),
            configuration_version=monitor.configuration_version,
        )
        db.add(run)
        db.flush()
        return run.id


def run_is_outdated(run: CheckRun, monitor: Monitor, now: datetime) -> bool:
    return monitor.configuration_version != run.configuration_version or (
        run.trigger == "scheduled"
        and now >= run.scheduled_at + timedelta(seconds=monitor.interval_seconds)
    )


def cancel_run(run: CheckRun, now: datetime) -> None:
    run.state, run.completed_at = "cancelled", now
    run.next_attempt_at = run.lease_expires_at = None
    run.lease_token = None


def claim_run(engine: Engine, run_id: UUID) -> ProbeSpec | None:
    with Session(engine) as db, db.begin():
        monitor_id = db.scalar(select(CheckRun.monitor_id).where(CheckRun.id == run_id))
        if monitor_id is None:
            return None
        # All paths lock monitor before run; no locks or sessions survive the HTTP request.
        monitor = db.scalar(select(Monitor).where(Monitor.id == monitor_id).with_for_update())
        run = db.scalar(select(CheckRun).where(CheckRun.id == run_id).with_for_update())
        now = db.scalar(select(func.clock_timestamp()))
        assert run is not None and now is not None
        if run.state not in {"pending", "running"}:
            return None
        if run.state == "running" and run.lease_expires_at and run.lease_expires_at > now:
            return None
        if run.state == "pending" and run.next_attempt_at and run.next_attempt_at > now:
            return None
        user = db.get(User, monitor.user_id) if monitor else None
        if (
            monitor is None
            or not monitor.enabled
            or monitor.deleted_at is not None
            or run_is_outdated(run, monitor, now)
            or user is None
            or user.email_verified_at is None
        ):
            cancel_run(run, now)
            return None
        run.state, run.next_attempt_at = "running", None
        run.lease_token = uuid4()
        run.lease_expires_at = now + timedelta(seconds=LEASE_SECONDS)
        return ProbeSpec(
            run.id,
            monitor.id,
            monitor.configuration_version,
            monitor.url,
            monitor.method,
            monitor.expected_status,
            monitor.timeout_seconds,
            run.lease_token,
        )


def begin_run(engine: Engine, monitor_id: UUID) -> ProbeSpec:
    spec = claim_run(engine, create_pending_run(engine, monitor_id))
    if spec is None:
        raise RunError("The run is no longer eligible or another executor claimed it.")
    return spec


def finish_run(engine: Engine, spec: ProbeSpec, result: ProbeResult) -> UUID | None:
    with Session(engine) as db, db.begin():
        monitor = db.scalar(select(Monitor).where(Monitor.id == spec.monitor_id).with_for_update())
        run = db.scalar(select(CheckRun).where(CheckRun.id == spec.run_id).with_for_update())
        now = db.scalar(select(func.clock_timestamp()))
        assert now is not None
        if (
            run is None
            or run.state != "running"
            or run.lease_token != spec.lease_token
            or run.lease_expires_at is None
            or run.lease_expires_at <= now
        ):
            return None
        check = Check(run_id=run.id, attempt_number=1, **asdict(result))
        db.add(check)
        run.completed_at = result.finished_at
        run.final_outcome = result.outcome
        run.lease_token = None
        run.lease_expires_at = run.next_attempt_at = None
        stale = (
            monitor is None
            or not monitor.enabled
            or monitor.deleted_at is not None
            or run_is_outdated(run, monitor, now)
        )
        run.state = (
            "cancelled"
            if stale
            else "infrastructure_failed"
            if result.outcome == "infrastructure_failure"
            else "completed"
        )
        if not stale and result.outcome in {"success", "failure"}:
            assert monitor is not None
            monitor.last_completed_check_at = result.finished_at
            if run.trigger == "scheduled":
                monitor.last_scheduled_check_at = result.finished_at
            # Aggregate health and three-failure incident decisions arrive with the retry policy.
        db.flush()
        check_id = check.id
    logger.info(
        "probe_completed",
        extra={
            "event": "probe_completed",
            "run_id": str(spec.run_id),
            "monitor_id": str(spec.monitor_id),
            "outcome": result.outcome,
            "error_code": result.error_code,
            "duration_ms": result.duration_ms,
        },
    )
    return check_id


def run_monitor(
    engine: Engine, settings: Settings, monitor_id: UUID
) -> tuple[UUID, UUID | None, ProbeResult]:
    spec = begin_run(engine, monitor_id)
    result = execute_spec(spec, settings)
    check_id = finish_run(engine, spec, result)
    return spec.run_id, check_id, result


def execute_spec(spec: ProbeSpec, settings: Settings) -> ProbeResult:
    # Explicit sync/async boundary; no session or transaction survives across outbound I/O.
    try:
        result = asyncio.run(
            execute_probe(
                spec.url, spec.method, spec.expected_status, spec.timeout_seconds, settings
            )
        )
    except Exception:
        now = now_utc()
        result = ProbeResult(
            now,
            now,
            0,
            "infrastructure_failure",
            None,
            "infrastructure_error",
            ERROR_MESSAGES["infrastructure_error"],
        )
    return result
