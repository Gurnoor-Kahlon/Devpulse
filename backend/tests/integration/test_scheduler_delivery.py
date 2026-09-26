import os
import signal
import socket
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pytest
from pydantic import SecretStr
from redis import Redis
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import now_utc
from app.jobs.configuration import DISPATCH_TASK, create_celery
from app.jobs.dispatcher import dispatch_runs, reserve_work
from app.models.check import Check, CheckRun
from app.models.monitor import Monitor
from app.monitoring.runs import claim_run, finish_run
from tests.integration import test_worker_delivery as worker_fixtures
from tests.integration.test_probes import saved_monitor, success
from tests.integration.test_worker_delivery import (
    BACKEND,
    state,
    wait_for,
    worker,
    worker_environment,
)
from tests.probe_fixtures import fixture_server, fixture_settings

worker_engine = worker_fixtures.worker_engine
worker_settings = worker_fixtures.worker_settings

pytestmark = [pytest.mark.integration, pytest.mark.worker]


def test_real_beat_dispatches_through_maintenance_and_probe_queues(
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
        monitor_id = saved_monitor(worker_engine, f"http://127.0.0.1:{server.server_port}/ok")
        with (
            worker(worker_engine, settings, tmp_path / "maintenance.log", "maintenance"),
            worker(worker_engine, settings, tmp_path / "probes.log") as probe,
        ):
            with (tmp_path / "beat.log").open("wb") as output:
                beat = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "celery",
                        "-A",
                        "app.jobs.celery_app:celery_app",
                        "--quiet",
                        "beat",
                        "--loglevel=INFO",
                        "--schedule",
                        str(tmp_path / "beat-state"),
                        "--pidfile",
                        str(tmp_path / "beat.pid"),
                    ],
                    cwd=BACKEND,
                    env=worker_environment(worker_engine, settings),
                    stdout=output,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                try:

                    def completed():
                        with Session(worker_engine) as db:
                            return db.scalar(select(func.count()).select_from(Check)) == 1

                    wait_for(completed, beat)
                    assert probe.poll() is None
                finally:
                    os.killpg(beat.pid, signal.SIGTERM)
                    try:
                        beat.wait(timeout=8)
                    except subprocess.TimeoutExpired:
                        os.killpg(beat.pid, signal.SIGKILL)
                        beat.wait(timeout=5)
        with Session(worker_engine) as db:
            run = db.scalar(select(CheckRun))
            assert run.trigger == "scheduled" and run.state == "completed"
            assert db.get(Monitor, monitor_id).last_scheduled_check_at is not None
            assert db.get(Monitor, monitor_id).current_state == "unknown"
        assert len(server.hits) == 1


@pytest.mark.parametrize("loss", ["publication", "message", "dispatcher", "lease"])
def test_real_dispatcher_recovers_durable_work_automatically(
    worker_engine: Engine,
    worker_settings: Settings,
    tmp_path: Path,
    loss: str,
) -> None:
    with fixture_server() as (server, _):
        settings = worker_settings.model_copy(
            update={
                "probe_fixture_destinations": fixture_settings(server).probe_fixture_destinations
            }
        )
        saved_monitor(worker_engine, f"http://127.0.0.1:{server.server_port}/ok")
        old_spec = None
        if loss == "publication":
            with socket.socket() as unavailable:
                unavailable.bind(("127.0.0.1", 0))
                broken = settings.model_copy(
                    update={
                        "broker_url": SecretStr(
                            f"redis://127.0.0.1:{unavailable.getsockname()[1]}/0"
                        )
                    }
                )
                dispatch_runs(worker_engine, broken)
        elif loss == "message":
            dispatch_runs(worker_engine, settings)
            client = Redis.from_url(settings.broker_url.get_secret_value())
            try:
                assert client.delete(f"{settings.broker_key_prefix}probes") == 1
            finally:
                client.close()
        else:
            run_id = reserve_work(worker_engine)[0]
            if loss == "lease":
                old_spec = claim_run(worker_engine, run_id)
        with Session(worker_engine) as db, db.begin():
            run = db.scalar(select(CheckRun))
            run_id = run.id
            run.next_publish_at = now_utc() - timedelta(seconds=1)
            if loss == "lease":
                run.lease_expires_at = now_utc() - timedelta(seconds=1)
        with (
            worker(worker_engine, settings, tmp_path / "maintenance.log", "maintenance"),
            worker(worker_engine, settings, tmp_path / "recovered.log") as probe,
        ):
            app = create_celery(settings)
            try:
                app.send_task(DISPATCH_TASK, args=[], retry=False)
            finally:
                app.close()
            wait_for(lambda: state(worker_engine, run_id) == "completed", probe)
        if old_spec is not None:
            assert finish_run(worker_engine, old_spec, success()) is None
        with Session(worker_engine) as db:
            assert db.scalar(select(func.count()).select_from(CheckRun)) == 1
            assert db.scalar(select(func.count()).select_from(Check)) == 1
        assert len(server.hits) == 1
