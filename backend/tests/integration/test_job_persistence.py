from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from kombu.exceptions import OperationalError as BrokerError
from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import now_utc
from app.jobs import publisher, tasks
from app.models.check import Check, CheckRun
from app.models.monitor import Monitor
from app.monitoring.runs import RunError, claim_run, create_pending_run, finish_run
from tests.integration.test_probes import saved_monitor, success

pytestmark = pytest.mark.integration


@pytest.fixture
def job_engine(database_engine: Engine) -> Engine:
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    with database_engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    return database_engine


def pending(engine: Engine) -> UUID:
    return create_pending_run(engine, saved_monitor(engine, "https://example.com/health"))


def expire(engine: Engine, run_id: UUID) -> None:
    with Session(engine) as db, db.begin():
        db.get(CheckRun, run_id).lease_expires_at = now_utc() - timedelta(seconds=1)


def test_concurrent_delivery_claims_one_lease_and_keeps_attempt_identity(
    job_engine: Engine,
) -> None:
    run_id = pending(job_engine)
    with ThreadPoolExecutor(max_workers=4) as pool:
        specs = list(pool.map(lambda _: claim_run(job_engine, run_id), range(4)))
    assert sum(spec is not None for spec in specs) == 1
    spec = next(spec for spec in specs if spec)
    with ThreadPoolExecutor(max_workers=2) as pool:
        checks = list(pool.map(lambda _: finish_run(job_engine, spec, success()), range(2)))
    assert sum(check is not None for check in checks) == 1
    assert claim_run(job_engine, run_id) is None
    with Session(job_engine) as db:
        assert db.scalar(select(func.count()).select_from(Check)) == 1
        assert db.get(CheckRun, run_id).lease_token is None


def test_expired_worker_is_fenced_before_and_after_reclaim(job_engine: Engine) -> None:
    run_id = pending(job_engine)
    old = claim_run(job_engine, run_id)
    expire(job_engine, run_id)
    assert finish_run(job_engine, old, success()) is None
    new = claim_run(job_engine, run_id)
    assert old.lease_token != new.lease_token
    assert finish_run(job_engine, old, success()) is None
    assert finish_run(job_engine, new, success()) is not None
    with Session(job_engine) as db:
        assert db.scalar(select(func.count()).select_from(Check)) == 1


@pytest.mark.parametrize("change", ["pause", "archive", "edit"])
def test_queued_outdated_work_is_cancelled_without_an_outbound_attempt(
    job_engine: Engine, change: str
) -> None:
    run_id = pending(job_engine)
    with Session(job_engine) as db, db.begin():
        monitor = db.get(Monitor, db.get(CheckRun, run_id).monitor_id)
        monitor.configuration_version += 1
        if change != "edit":
            monitor.enabled = False
            monitor.next_due_at = None
        if change == "archive":
            monitor.deleted_at = now_utc()
    assert claim_run(job_engine, run_id) is None
    with Session(job_engine) as db:
        run = db.get(CheckRun, run_id)
        assert run.state == "cancelled" and run.lease_token is None
        assert db.scalar(select(func.count()).select_from(Check)) == 0


def test_future_pending_work_and_existing_pending_monitor_are_not_reclaimed(
    job_engine: Engine,
) -> None:
    run_id = pending(job_engine)
    with Session(job_engine) as db, db.begin():
        run = db.get(CheckRun, run_id)
        run.next_attempt_at = now_utc() + timedelta(minutes=1)
        monitor_id = run.monitor_id
    assert claim_run(job_engine, run_id) is None
    with pytest.raises(RunError):
        create_pending_run(job_engine, monitor_id)


def test_publish_failure_leaves_durable_pending_work_without_holding_a_transaction(
    job_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = pending(job_engine)
    app = Mock()

    def unavailable() -> None:
        assert job_engine.pool.checkedout() == 0
        raise BrokerError("redis-password-canary")

    app.connection_for_write.side_effect = unavailable
    monkeypatch.setattr(publisher, "create_celery", lambda settings: app)
    assert publisher.publish_run(job_engine, Settings(), run_id) is False
    with Session(job_engine) as db:
        assert db.get(CheckRun, run_id).state == "pending"
        assert db.scalar(select(func.count()).select_from(Check)) == 0
    assert app.close.called


def test_database_failure_after_probe_preserves_recoverable_run(
    job_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sqlalchemy.exc import OperationalError

    run_id = pending(job_engine)
    monkeypatch.setattr(tasks, "create_database_engine", lambda settings: job_engine)
    probe = Mock(return_value=success())
    monkeypatch.setattr(tasks, "execute_spec", probe)
    with monkeypatch.context() as patch:
        patch.setattr(tasks, "finish_run", Mock(side_effect=OperationalError("", {}, Exception())))
        tasks.execute_job(str(run_id))
    with Session(job_engine) as db:
        assert db.get(CheckRun, run_id).state == "running"
        assert db.scalar(select(func.count()).select_from(Check)) == 0
        assert db.get(Monitor, db.get(CheckRun, run_id).monitor_id).last_completed_check_at is None
    expire(job_engine, run_id)
    tasks.execute_job(str(run_id))
    assert probe.call_count == 2  # Network work may repeat; stored attempts do not.
    with Session(job_engine) as db:
        assert db.get(CheckRun, run_id).state == "completed"
        assert db.scalar(select(func.count()).select_from(Check)) == 1


def test_lease_migration_preserves_history_and_recovers_old_active_runs(
    database_engine: Engine,
) -> None:
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    with database_engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "277e61607ff2")
    # Use SQL for the old schema: current ORM includes the new lease columns.
    monitor_id, user_id = uuid4(), uuid4()
    with database_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id, email, password_hash, email_verified_at) "
                "VALUES (:id, 'migration@example.com', 'unused', CURRENT_TIMESTAMP)"
            ),
            {"id": user_id},
        )
        connection.execute(
            text(
                "INSERT INTO monitors (id, user_id, name, url, method, expected_status, "
                "interval_seconds, timeout_seconds, enabled, configuration_version, next_due_at, "
                "current_state) "
                "VALUES (:id, :user, 'Legacy', 'https://example.com', 'GET', 200, 60, 5, true, 1, "
                "CURRENT_TIMESTAMP, 'unknown')"
            ),
            {"id": monitor_id, "user": user_id},
        )
    with database_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO check_runs "
                "(id, monitor_id, scheduled_at, configuration_version, trigger, state) "
                "VALUES (gen_random_uuid(), :monitor, CURRENT_TIMESTAMP, 1, 'manual', 'running')"
            ),
            {"monitor": monitor_id},
        )
    with database_engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        command.check(config)
    with Session(database_engine) as db:
        run = db.scalar(select(CheckRun))
        assert run.state == "pending" and run.next_attempt_at is not None
        assert run.lease_token is None


def test_clock_correction_during_http_does_not_strand_a_worker_run(
    job_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.monitoring import executor
    from tests.probe_fixtures import fixture_server, fixture_settings

    with fixture_server() as (server, _):
        run_id = create_pending_run(
            job_engine, saved_monitor(job_engine, f"http://127.0.0.1:{server.server_port}/ok")
        )
        start = now_utc()
        wall_times = iter((start, start - timedelta(seconds=2)))
        monkeypatch.setattr(executor, "now_utc", lambda: next(wall_times))
        monkeypatch.setattr(tasks, "load_settings", lambda: fixture_settings(server))
        monkeypatch.setattr(tasks, "create_database_engine", lambda settings: job_engine)
        tasks.execute_job(str(run_id))
        with Session(job_engine) as db:
            assert db.get(CheckRun, run_id).state == "completed"
            check = db.scalar(select(Check).where(Check.run_id == run_id))
            assert check.finished_at >= check.started_at
            assert check.duration_ms > 0
        assert len(server.hits) == 1
