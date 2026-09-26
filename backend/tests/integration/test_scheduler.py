from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import now_utc
from app.jobs import dispatcher
from app.jobs.dispatcher import BATCH_SIZE, dispatch_runs, reserve_work
from app.models.auth import User
from app.models.check import Check, CheckRun
from app.models.monitor import Monitor
from app.monitoring.runs import claim_run, create_pending_run, finish_run
from app.schemas.monitors import MonitorResponse, MonitorUpdate
from app.services.monitors import update_monitor
from tests.integration.test_probes import success

pytestmark = pytest.mark.integration


@pytest.fixture
def scheduler_engine(database_engine: Engine) -> Engine:
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    with database_engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    return database_engine


def monitors(engine: Engine, count: int = 1) -> list:
    with Session(engine) as db, db.begin():
        user = User(
            email=f"{uuid4().hex}@example.com", password_hash="unused", email_verified_at=now_utc()
        )
        db.add(user)
        db.flush()
        rows = [
            Monitor(
                user_id=user.id,
                name="Scheduled",
                url="https://example.com",
                next_due_at=now_utc() - timedelta(hours=2),
            )
            for _ in range(count)
        ]
        db.add_all(rows)
        db.flush()
        return [row.id for row in rows]


def test_overlapping_dispatchers_schedule_once_without_replaying_missed_intervals(
    scheduler_engine: Engine,
) -> None:
    ids = monitors(scheduler_engine, 40)
    with ThreadPoolExecutor(max_workers=4) as pool:
        batches = list(pool.map(lambda _: reserve_work(scheduler_engine), range(4)))
    run_ids = [run for batch in batches for run in batch]
    assert len(run_ids) == len(set(run_ids)) == len(ids)
    assert all(len(batch) <= BATCH_SIZE for batch in batches)
    with Session(scheduler_engine) as db:
        now = db.scalar(select(func.clock_timestamp()))
        for monitor in db.scalars(select(Monitor)):
            assert now < monitor.next_due_at <= now + timedelta(seconds=60)
        for run in db.scalars(select(CheckRun)):
            assert run.trigger == "scheduled" and run.state == "pending"
            assert now - timedelta(seconds=10) < run.scheduled_at <= now
    assert reserve_work(scheduler_engine) == []


def test_locked_monitors_are_skipped_and_batch_is_bounded(scheduler_engine: Engine) -> None:
    ids = monitors(scheduler_engine, 30)
    with Session(scheduler_engine) as locked, locked.begin():
        locked.execute(select(Monitor).where(Monitor.id == ids[0]).with_for_update())
        first = reserve_work(scheduler_engine)
        assert len(first) == BATCH_SIZE
        with Session(scheduler_engine) as db:
            assert db.scalar(select(CheckRun.id).where(CheckRun.monitor_id == ids[0])) is None
        assert len(reserve_work(scheduler_engine)) == 4
    assert len(reserve_work(scheduler_engine)) == 1


def test_publication_failure_and_dispatcher_crash_are_reconciled_after_cooldown(
    scheduler_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monitors(scheduler_engine, 3)
    called = []

    def unavailable(engine, settings, run_id):
        assert engine.pool.checkedout() == 0
        called.append(run_id)
        return False

    monkeypatch.setattr(dispatcher, "publish_run", unavailable)
    dispatch_runs(scheduler_engine, Settings(environment="test"))
    assert len(called) == 1
    assert reserve_work(scheduler_engine) == []
    with Session(scheduler_engine) as db, db.begin():
        original = set(db.scalars(select(CheckRun.id)))
        assert len(original) == 3
        for run in db.scalars(select(CheckRun)):
            assert run.state == "pending"
            run.next_publish_at = now_utc() - timedelta(seconds=1)
    # This also models a dispatcher dying after reservation commit, before publication.
    assert set(reserve_work(scheduler_engine)) == original
    assert reserve_work(scheduler_engine) == []


def test_reconciliation_does_not_steal_live_leases_or_future_attempts(
    scheduler_engine: Engine,
) -> None:
    ids = monitors(scheduler_engine, 2)
    first = create_pending_run(scheduler_engine, ids[0])
    second = create_pending_run(scheduler_engine, ids[1])
    old = claim_run(scheduler_engine, first)
    with Session(scheduler_engine) as db, db.begin():
        db.get(CheckRun, second).next_attempt_at = now_utc() + timedelta(hours=1)
    assert reserve_work(scheduler_engine) == []
    with Session(scheduler_engine) as db, db.begin():
        db.get(CheckRun, first).lease_expires_at = now_utc() - timedelta(seconds=1)
    assert reserve_work(scheduler_engine) == [first]
    new = claim_run(scheduler_engine, first)
    assert old.lease_token != new.lease_token
    assert finish_run(scheduler_engine, old, success()) is None
    assert finish_run(scheduler_engine, new, success()) is not None


@pytest.mark.parametrize("change", ["pause", "archive", "unverify", "edit", "late"])
def test_obsolete_work_is_cancelled_and_cannot_execute(
    scheduler_engine: Engine, change: str
) -> None:
    identifier = monitors(scheduler_engine)[0]
    run_id = reserve_work(scheduler_engine)[0]
    with Session(scheduler_engine) as db, db.begin():
        monitor = db.get(Monitor, identifier)
        run = db.get(CheckRun, run_id)
        run.next_publish_at = now_utc() - timedelta(seconds=1)
        if change in {"pause", "archive"}:
            monitor.enabled, monitor.next_due_at = False, None
            if change == "archive":
                monitor.deleted_at = now_utc()
        elif change == "unverify":
            db.get(User, monitor.user_id).email_verified_at = None
        elif change == "edit":
            monitor.configuration_version += 1
        else:
            run.scheduled_at = now_utc() - timedelta(minutes=5)
            monitor.next_due_at = now_utc() - timedelta(minutes=4)
    recovered = reserve_work(scheduler_engine)
    assert run_id not in recovered
    assert claim_run(scheduler_engine, run_id) is None
    with Session(scheduler_engine) as db:
        assert db.get(CheckRun, run_id).state == "cancelled"
        assert db.scalar(select(func.count()).select_from(Check)) == 0
    assert len(recovered) == (1 if change == "late" else 0)


def test_late_message_and_late_completion_are_rejected_without_a_dispatcher(
    scheduler_engine: Engine,
) -> None:
    monitors(scheduler_engine, 2)
    first, second = reserve_work(scheduler_engine)
    spec = claim_run(scheduler_engine, second)
    with Session(scheduler_engine) as db, db.begin():
        for run in db.scalars(select(CheckRun)):
            run.scheduled_at = now_utc() - timedelta(minutes=2)
    assert claim_run(scheduler_engine, first) is None
    assert finish_run(scheduler_engine, spec, success()) is not None
    with Session(scheduler_engine) as db:
        assert {run.state for run in db.scalars(select(CheckRun))} == {"cancelled"}
        assert all(m.last_scheduled_check_at is None for m in db.scalars(select(Monitor)))


def test_freshness_is_separate_from_health_and_manual_checks(scheduler_engine: Engine) -> None:
    identifier = monitors(scheduler_engine)[0]
    with Session(scheduler_engine) as db, db.begin():
        monitor = db.get(Monitor, identifier)
        monitor.updated_at = now_utc() - timedelta(minutes=5)
        monitor.current_state = "operational"
        assert MonitorResponse.model_validate(monitor).observation_status == "stale"
    manual = claim_run(scheduler_engine, create_pending_run(scheduler_engine, identifier))
    finish_run(scheduler_engine, manual, success())
    with Session(scheduler_engine) as db:
        monitor = db.get(Monitor, identifier)
        assert monitor.last_completed_check_at is not None
        assert MonitorResponse.model_validate(monitor).observation_status == "stale"
    scheduled = claim_run(scheduler_engine, reserve_work(scheduler_engine)[0])
    finish_run(scheduler_engine, scheduled, success())
    with Session(scheduler_engine) as db:
        monitor = db.get(Monitor, identifier)
        assert MonitorResponse.model_validate(monitor).observation_status == "current"
        assert monitor.current_state == "operational"
        paused = update_monitor(
            db, monitor.user_id, identifier, MonitorUpdate(configuration_version=1, enabled=False)
        )
        assert MonitorResponse.model_validate(paused).observation_status == "paused"
        resumed = update_monitor(
            db, monitor.user_id, identifier, MonitorUpdate(configuration_version=2, enabled=True)
        )
        assert MonitorResponse.model_validate(resumed).observation_status == "awaiting_check"
        assert resumed.last_completed_check_at is not None


def test_scheduler_migration_preserves_m10_pending_rows(database_engine: Engine) -> None:
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    with database_engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "b31d8e0c6a10")
        connection.execute(
            text(
                "INSERT INTO users(id, email, password_hash) VALUES (:id, 'old@example.com', "
                "'unused')"
            ),
            {"id": (owner := uuid4())},
        )
        connection.execute(
            text(
                "INSERT INTO "
                "monitors(id,user_id,name,url,method,expected_status,interval_seconds,"
                "timeout_seconds,enabled,configuration_version,next_due_at,current_state) VALUES "
                "(:id,:owner,'Old','https://example.com','GET',200,60,5,true,1,CURRENT_TIMESTAMP,"
                "'unknown')"
            ),
            {"id": (monitor := uuid4()), "owner": owner},
        )
        connection.execute(
            text(
                "INSERT INTO "
                "check_runs(id,monitor_id,scheduled_at,configuration_version,trigger,state,"
                "next_attempt_at) VALUES "
                "(:id,:monitor,CURRENT_TIMESTAMP,1,'manual','pending',CURRENT_TIMESTAMP)"
            ),
            {"id": (run := uuid4()), "monitor": monitor},
        )
        connection.commit()
        command.upgrade(config, "head")
        command.check(config)
        assert (
            connection.scalar(select(CheckRun.next_publish_at).where(CheckRun.id == run))
            is not None
        )
        connection.commit()
        command.downgrade(config, "b31d8e0c6a10")
        assert connection.scalar(text("SELECT count(*) FROM check_runs")) == 1
        connection.commit()
        command.upgrade(config, "head")
        command.check(config)


def test_only_due_verified_enabled_idle_monitors_are_scheduled(scheduler_engine: Engine) -> None:
    ids = monitors(scheduler_engine, 6)
    manual = create_pending_run(scheduler_engine, ids[5])
    assert claim_run(scheduler_engine, manual) is not None
    with Session(scheduler_engine) as db, db.begin():
        db.get(Monitor, ids[1]).next_due_at = now_utc() + timedelta(hours=1)
        for identifier in ids[2:4]:
            monitor = db.get(Monitor, identifier)
            monitor.enabled, monitor.next_due_at = False, None
        db.get(Monitor, ids[3]).deleted_at = now_utc()
        unverified = User(email="unverified-scheduler@example.com", password_hash="unused")
        db.add(unverified)
        db.flush()
        db.get(Monitor, ids[4]).user_id = unverified.id
    scheduled = reserve_work(scheduler_engine)
    assert len(scheduled) == 1
    with Session(scheduler_engine) as db:
        assert db.get(CheckRun, scheduled[0]).monitor_id == ids[0]
        assert db.scalar(select(func.count()).select_from(CheckRun)) == 2
