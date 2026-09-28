import json
import os
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from pydantic import SecretStr
from redis import Redis
from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.logging import configure_logging
from app.core.security import now_utc
from app.jobs.publisher import publish_run
from app.models.check import Check, CheckRun
from app.models.monitor import Monitor
from app.monitoring.runs import create_pending_run
from tests.integration.test_probes import saved_monitor
from tests.probe_fixtures import fixture_server, fixture_settings

pytestmark = [pytest.mark.integration, pytest.mark.worker]
BACKEND = Path(__file__).resolve().parents[2]


def wait_for(predicate: Callable[[], bool], process: subprocess.Popen[bytes] | None = None) -> None:
    end = time.monotonic() + 25
    while time.monotonic() < end:
        if predicate():
            return
        if process is not None and process.poll() is not None:
            pytest.fail("The Linux test worker exited unexpectedly; inspect its sanitized log.")
        time.sleep(0.05)
    pytest.fail("Worker test condition was not reached within 25 seconds.")


@pytest.fixture
def worker_settings(database_settings: Settings) -> Iterator[Settings]:
    if sys.platform != "linux":
        pytest.fail("--run-worker requires Linux; Windows solo workers are not equivalent.")
    broker = os.environ.get("TEST_REDIS_URL")
    if not broker:
        pytest.fail("Set TEST_REDIS_URL to a dedicated local Redis test service.")
    settings = Settings(
        environment="test",
        database_url=database_settings.database_url,
        broker_url=SecretStr(broker),
        broker_key_prefix=f"devpulse_test_{uuid4().hex}:",
    )
    client = Redis.from_url(broker, socket_connect_timeout=3, socket_timeout=3)
    try:
        assert client.ping()
        yield settings
    finally:
        # Never FLUSHDB: delete only keys under this test's randomly generated prefix.
        try:
            for key in client.scan_iter(match=f"{settings.broker_key_prefix}*"):
                client.delete(key)
        finally:
            client.close()


@pytest.fixture
def worker_engine(database_engine: Engine) -> Engine:
    config = Config(str(BACKEND / "alembic.ini"))
    with database_engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    return database_engine


def worker_environment(engine: Engine, settings: Settings) -> dict[str, str]:
    with engine.connect() as connection:
        schema = connection.scalar(text("SELECT current_schema()"))
    env = {key: value for key, value in os.environ.items() if not key.startswith("DEVPULSE_")}
    env.update(
        {
            "DEVPULSE_ENVIRONMENT": "test",
            "DEVPULSE_DATABASE_URL": settings.database_url.get_secret_value(),
            "DEVPULSE_BROKER_URL": settings.broker_url.get_secret_value(),
            "DEVPULSE_BROKER_KEY_PREFIX": settings.broker_key_prefix,
            "DEVPULSE_PROBE_FIXTURE_DESTINATIONS": json.dumps(
                [entry.model_dump() for entry in settings.probe_fixture_destinations]
            ),
            "TEST_WORKER_SCHEMA": schema,
            "DEVPULSE_SMTP_HOST": settings.smtp_host,
            "DEVPULSE_SMTP_PORT": str(settings.smtp_port),
            "DEVPULSE_SMTP_MODE": settings.smtp_mode,
            "DEVPULSE_SMTP_USERNAME": "",
            "DEVPULSE_SMTP_PASSWORD": "",
            "DEVPULSE_MAIL_FROM": str(settings.mail_from),
        }
    )
    return env


@contextmanager
def worker(
    engine: Engine, settings: Settings, log: Path, queues: str = "probes"
) -> Iterator[subprocess.Popen[bytes]]:
    env = worker_environment(engine, settings)
    with log.open("wb") as output:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "celery",
                "-A",
                "tests.worker_app:celery_app",
                "--quiet",
                "worker",
                "--pool=prefork",
                f"--queues={queues}",
                "--concurrency=2",
                "--without-gossip",
                "--without-mingle",
                "--without-heartbeat",
                "--loglevel=INFO",
            ],
            cwd=BACKEND,
            env=env,
            stdout=output,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            wait_for(lambda: bool(events(log, "worker_ready")), process)
            yield process
        finally:
            # This process owns the new session/group, including its prefork children.
            try:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
            except ProcessLookupError:
                process.wait(timeout=5)


def events(log: Path, event: str) -> list[dict[str, object]]:
    records = []
    for line in log.read_text().splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue  # Shutdown notices and an incomplete concurrent write are not records.
        if record.get("event") == event:
            records.append(record)
    return records


def state(engine: Engine, run_id: UUID) -> str:
    with Session(engine) as db:
        return db.get(CheckRun, run_id).state


def test_real_broker_duplicate_delivery_stores_one_attempt(
    worker_engine: Engine, worker_settings: Settings, tmp_path: Path
) -> None:
    with fixture_server() as (server, _):
        settings = worker_settings.model_copy(
            update={
                "probe_fixture_destinations": fixture_settings(server).probe_fixture_destinations
            }
        )
        run_id = create_pending_run(
            worker_engine,
            saved_monitor(
                worker_engine,
                f"http://127.0.0.1:{server.server_port}/json?key=worker-query-canary",
            ),
        )
        for _ in range(4):
            assert publish_run(worker_engine, settings, run_id)
        with worker(worker_engine, settings, tmp_path / "duplicates.log") as process:
            wait_for(lambda: state(worker_engine, run_id) == "completed", process)
            # The same queue FIFO ensures the three duplicate messages precede this later run.
            with Session(worker_engine) as db:
                monitor_id = db.get(CheckRun, run_id).monitor_id
            later_id = create_pending_run(worker_engine, monitor_id)
            assert publish_run(worker_engine, settings, later_id)
            wait_for(lambda: state(worker_engine, later_id) == "completed", process)
        with Session(worker_engine) as db:
            assert (
                db.scalar(select(func.count()).select_from(Check).where(Check.run_id == run_id))
                == 1
            )
        assert len(server.hits) == 2
        log = tmp_path / "duplicates.log"
        output = log.read_text()
        assert "worker-query-canary" not in output and "response-secret-canary" not in output
        started = [entry for entry in events(log, "job_started") if entry["run_id"] == str(run_id)]
        finished = [
            entry for entry in events(log, "job_finished") if entry["run_id"] == str(run_id)
        ]
        assert len(started) == len(finished) == 1
        assert UUID(str(started[0]["job_id"]))
        assert finished[0]["job_id"] == started[0]["job_id"]
        assert finished[0]["outcome"] == "stored"
        assert len(events(log, "job_ignored")) == 3
        client = Redis.from_url(settings.broker_url.get_secret_value())
        try:
            assert not list(client.scan_iter(match=f"{settings.broker_key_prefix}*task-meta*"))
        finally:
            client.close()


def test_lost_message_is_republished_from_postgresql(
    worker_engine: Engine, worker_settings: Settings, tmp_path: Path
) -> None:
    with fixture_server() as (server, _):
        settings = worker_settings.model_copy(
            update={
                "probe_fixture_destinations": fixture_settings(server).probe_fixture_destinations
            }
        )
        run_id = create_pending_run(
            worker_engine, saved_monitor(worker_engine, f"http://127.0.0.1:{server.server_port}/ok")
        )
        assert publish_run(worker_engine, settings, run_id)
        client = Redis.from_url(settings.broker_url.get_secret_value())
        try:
            assert client.delete(f"{settings.broker_key_prefix}probes") == 1
        finally:
            client.close()
        assert state(worker_engine, run_id) == "pending"
        assert publish_run(worker_engine, settings, run_id)
        with worker(worker_engine, settings, tmp_path / "republish.log") as process:
            wait_for(lambda: state(worker_engine, run_id) == "completed", process)
        assert len(server.hits) == 1


def test_killed_prefork_worker_recovers_after_lease_expiry(
    worker_engine: Engine, worker_settings: Settings, tmp_path: Path
) -> None:
    with fixture_server() as (server, _):
        settings = worker_settings.model_copy(
            update={
                "probe_fixture_destinations": fixture_settings(server).probe_fixture_destinations
            }
        )
        run_id = create_pending_run(
            worker_engine,
            saved_monitor(worker_engine, f"http://127.0.0.1:{server.server_port}/slow"),
        )
        assert publish_run(worker_engine, settings, run_id)
        with worker(worker_engine, settings, tmp_path / "killed.log") as process:
            wait_for(lambda: len(server.hits) == 1, process)
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
        assert state(worker_engine, run_id) == "running"
        with Session(worker_engine) as db, db.begin():
            db.get(CheckRun, run_id).lease_expires_at = now_utc() - timedelta(seconds=1)
        assert publish_run(worker_engine, settings, run_id)
        with worker(worker_engine, settings, tmp_path / "recovered.log") as process:
            wait_for(lambda: state(worker_engine, run_id) == "completed", process)
        with Session(worker_engine) as db:
            assert db.scalar(select(func.count()).select_from(Check)) == 1
        assert len(server.hits) == 2


def test_real_broker_publication_failure_keeps_pending_run_for_republish(
    worker_engine: Engine,
    worker_settings: Settings,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with fixture_server() as (server, _):
        settings = worker_settings.model_copy(
            update={
                "probe_fixture_destinations": fixture_settings(server).probe_fixture_destinations
            }
        )
        run_id = create_pending_run(
            worker_engine, saved_monitor(worker_engine, f"http://127.0.0.1:{server.server_port}/ok")
        )
        # Reserve a local port without listening; no existing Redis service is stopped.
        with socket.socket() as unavailable:
            unavailable.bind(("127.0.0.1", 0))
            broken = settings.model_copy(
                update={
                    "broker_url": SecretStr(
                        f"redis://:broker-secret-canary@127.0.0.1:{unavailable.getsockname()[1]}/0"
                    )
                }
            )
            configure_logging("INFO")
            start = time.monotonic()
            assert not publish_run(worker_engine, broken, run_id)
            assert time.monotonic() - start < 10
        output = capsys.readouterr().out
        assert "job_publish_failed" in output and "broker-secret-canary" not in output
        assert state(worker_engine, run_id) == "pending"
        assert not server.hits
        assert publish_run(worker_engine, settings, run_id)
        with worker(worker_engine, settings, tmp_path / "publication-recovery.log") as process:
            wait_for(lambda: state(worker_engine, run_id) == "completed", process)
        assert len(server.hits) == 1


def test_killed_child_is_redelivered_without_overwriting_live_lease(
    worker_engine: Engine,
    worker_settings: Settings,
    tmp_path: Path,
) -> None:
    with fixture_server() as (server, _):
        settings = worker_settings.model_copy(
            update={
                "probe_fixture_destinations": fixture_settings(server).probe_fixture_destinations
            }
        )
        run_id = create_pending_run(
            worker_engine,
            saved_monitor(worker_engine, f"http://127.0.0.1:{server.server_port}/slow"),
        )
        log = tmp_path / "child-loss.log"
        with worker(worker_engine, settings, log) as process:
            assert publish_run(worker_engine, settings, run_id)
            wait_for(lambda: bool(server.hits) and bool(events(log, "job_started")), process)
            child_pid = int(events(log, "job_started")[0]["worker_pid"])
            assert child_pid != process.pid
            assert os.getpgid(child_pid) == process.pid
            os.kill(child_pid, signal.SIGKILL)
            # Late acknowledgment + reject-on-loss redelivers, but the lease is still fenced.
            wait_for(lambda: bool(events(log, "job_ignored")), process)
            assert process.poll() is None
            assert state(worker_engine, run_id) == "running"
            assert len(server.hits) == 1
            with Session(worker_engine) as db, db.begin():
                assert db.scalar(select(func.count()).select_from(Check)) == 0
                db.get(CheckRun, run_id).lease_expires_at = now_utc() - timedelta(seconds=1)
            assert publish_run(worker_engine, settings, run_id)
            wait_for(lambda: state(worker_engine, run_id) == "completed", process)
        with Session(worker_engine) as db:
            assert db.scalar(select(func.count()).select_from(Check)) == 1
        assert len(server.hits) == 2


def test_real_database_lock_failure_after_http_leaves_recoverable_lease(
    worker_engine: Engine,
    worker_settings: Settings,
    tmp_path: Path,
) -> None:
    with fixture_server() as (server, _):
        settings = worker_settings.model_copy(
            update={
                "probe_fixture_destinations": fixture_settings(server).probe_fixture_destinations
            }
        )
        monitor_id = saved_monitor(worker_engine, f"http://127.0.0.1:{server.server_port}/slow")
        run_id = create_pending_run(worker_engine, monitor_id)
        log = tmp_path / "database-failure.log"
        with worker(worker_engine, settings, log) as process:
            assert publish_run(worker_engine, settings, run_id)
            wait_for(lambda: bool(server.hits), process)
            # Hold only this fixture monitor's row beyond the worker's database lock timeout.
            with Session(worker_engine) as blocker, blocker.begin():
                blocker.execute(select(Monitor).where(Monitor.id == monitor_id).with_for_update())
                wait_for(lambda: bool(events(log, "job_deferred")), process)
            with Session(worker_engine) as db, db.begin():
                run = db.get(CheckRun, run_id)
                assert run.state == "running" and run.final_outcome is None
                assert db.scalar(select(func.count()).select_from(Check)) == 0
                assert db.get(Monitor, monitor_id).last_completed_check_at is None
                run.lease_expires_at = now_utc() - timedelta(seconds=1)
            assert publish_run(worker_engine, settings, run_id)
            wait_for(lambda: state(worker_engine, run_id) == "completed", process)
        with Session(worker_engine) as db:
            assert db.scalar(select(func.count()).select_from(Check)) == 1
        assert len(server.hits) == 2
        assert events(log, "job_deferred")[0]["error_code"] == "persistence_unavailable"
