"""Database-driven scheduling. Redis publication always occurs after commit."""

import time
from datetime import timedelta
from uuid import UUID

from sqlalchemy import Engine, and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.logging import logger
from app.jobs.publisher import publish_run
from app.models.auth import User
from app.models.check import CheckRun
from app.models.monitor import Monitor
from app.monitoring.runs import RunError, cancel_run, run_is_outdated

BATCH_SIZE = 25
REPUBLISH_SECONDS = 30
PUBLICATION_BUDGET_SECONDS = 15


def reserve_work(engine: Engine) -> list[UUID]:
    """Reserve at most 25 recoveries + 25 new runs under short row locks."""
    ids: list[UUID] = []
    with Session(engine) as db, db.begin():
        now = db.scalar(select(func.clock_timestamp()))
        assert now is not None
        recovery = db.scalars(
            select(Monitor)
            .join(CheckRun, CheckRun.monitor_id == Monitor.id)
            .where(
                CheckRun.next_publish_at <= now,
                or_(
                    and_(CheckRun.state == "pending", CheckRun.next_attempt_at <= now),
                    and_(CheckRun.state == "running", CheckRun.lease_expires_at <= now),
                ),
            )
            .order_by(CheckRun.next_publish_at, CheckRun.id)
            .limit(BATCH_SIZE)
            .with_for_update(of=Monitor, skip_locked=True)
        ).all()
        for monitor in recovery:
            # Workers and API mutations also take the monitor lock first.
            run = db.scalar(
                select(CheckRun)
                .where(
                    CheckRun.monitor_id == monitor.id, CheckRun.state.in_(("pending", "running"))
                )
                .with_for_update()
            )
            assert run is not None
            user = db.get(User, monitor.user_id)
            if (
                not monitor.enabled
                or monitor.deleted_at is not None
                or user is None
                or user.email_verified_at is None
                or run_is_outdated(run, monitor, now)
            ):
                cancel_run(run, now, monitor)
                continue
            run.next_publish_at = now + timedelta(seconds=REPUBLISH_SECONDS)
            ids.append(run.id)
        db.flush()  # Cancelled runs release the active-run uniqueness constraint.
        active = (
            select(CheckRun.id)
            .where(CheckRun.monitor_id == Monitor.id, CheckRun.state.in_(("pending", "running")))
            .exists()
        )
        due = db.scalars(
            select(Monitor)
            .join(User, User.id == Monitor.user_id)
            .where(
                Monitor.enabled.is_(True),
                Monitor.deleted_at.is_(None),
                Monitor.next_due_at <= now,
                User.email_verified_at.is_not(None),
                ~active,
            )
            .order_by(Monitor.next_due_at, Monitor.id)
            .limit(BATCH_SIZE)
            .with_for_update(of=Monitor, skip_locked=True)
        ).all()
        for monitor in due:
            # One observation now; never manufacture or replay missed historical intervals.
            run = CheckRun(
                monitor_id=monitor.id,
                scheduled_at=now,
                configuration_version=monitor.configuration_version,
                trigger="scheduled",
                next_attempt_at=now,
                next_publish_at=now + timedelta(seconds=REPUBLISH_SECONDS),
            )
            db.add(run)
            monitor.next_due_at = now + timedelta(seconds=monitor.interval_seconds)
            db.flush()
            ids.append(run.id)
    return ids


def dispatch_runs(engine: Engine, settings: Settings) -> None:
    ids = reserve_work(engine)
    end = time.monotonic() + PUBLICATION_BUDGET_SECONDS
    published = 0
    for run_id in ids:
        if time.monotonic() >= end:
            break  # Unpublished reservations become eligible after their short cooldown.
        try:
            if not publish_run(engine, settings, run_id):
                break  # Avoid multiplying broker outage timeouts across the batch.
            published += 1
        except RunError:
            continue  # Another delivery completed/cancelled this identity after commit.
    logger.info(
        "scheduler_dispatched",
        extra={
            "event": "scheduler_dispatched",
            "reserved_count": len(ids),
            "published_count": published,
        },
    )
