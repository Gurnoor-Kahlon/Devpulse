import asyncio
from dataclasses import asdict, dataclass
from uuid import UUID

from sqlalchemy import Engine, select
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


def begin_run(engine: Engine, monitor_id: UUID) -> ProbeSpec:
    with Session(engine) as db, db.begin():
        monitor = db.scalar(select(Monitor).where(Monitor.id == monitor_id).with_for_update())
        if monitor is None or not monitor.enabled or monitor.deleted_at is not None:
            raise RunError("Monitor is unavailable or paused.")
        user = db.get(User, monitor.user_id)
        if user is None or user.email_verified_at is None:
            raise RunError("The monitor owner must verify their email.")
        if db.scalar(
            select(CheckRun.id).where(
                CheckRun.monitor_id == monitor_id, CheckRun.state == "running"
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
        return ProbeSpec(
            run.id,
            monitor.id,
            monitor.configuration_version,
            monitor.url,
            monitor.method,
            monitor.expected_status,
            monitor.timeout_seconds,
        )


def finish_run(engine: Engine, spec: ProbeSpec, result: ProbeResult) -> UUID | None:
    with Session(engine) as db, db.begin():
        monitor = db.scalar(select(Monitor).where(Monitor.id == spec.monitor_id).with_for_update())
        run = db.scalar(select(CheckRun).where(CheckRun.id == spec.run_id).with_for_update())
        if run is None or run.state != "running":
            return None
        check = Check(run_id=run.id, attempt_number=1, **asdict(result))
        db.add(check)
        run.completed_at = result.finished_at
        run.final_outcome = result.outcome
        stale = (
            monitor is None
            or not monitor.enabled
            or monitor.deleted_at is not None
            or monitor.configuration_version != spec.configuration_version
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
    check_id = finish_run(engine, spec, result)
    return spec.run_id, check_id, result
