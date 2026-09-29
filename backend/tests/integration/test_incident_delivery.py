import time
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import now_utc
from app.jobs.dispatcher import dispatch_runs
from app.models.assertion import Assertion
from app.models.check import Check, CheckRun
from app.models.incident import Incident
from app.models.monitor import Monitor
from tests.integration import test_worker_delivery as worker_fixtures
from tests.integration.test_probes import saved_monitor
from tests.integration.test_worker_delivery import wait_for, worker
from tests.probe_fixtures import fixture_server, fixture_settings

worker_engine = worker_fixtures.worker_engine
worker_settings = worker_fixtures.worker_settings
pytestmark = [pytest.mark.integration, pytest.mark.worker]


@pytest.mark.parametrize("assertion_failure", [False, True])
def test_real_ten_second_retries_survive_restart_confirm_and_recover(
    assertion_failure: bool,
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
        route = "assertion-controlled" if assertion_failure else "controlled"
        mid = saved_monitor(
            worker_engine,
            f"http://127.0.0.1:{server.server_port}/{route}?token=retry-query-canary",
        )

        if assertion_failure:
            with Session(worker_engine) as db, db.begin():
                db.add(
                    Assertion(
                        monitor_id=mid, position=0, kind="json_equals", pointer="/ok", expected=True
                    )
                )

        def attempts():
            with Session(worker_engine) as db:
                return db.scalar(select(func.count()).select_from(Check))

        with worker(worker_engine, settings, tmp_path / "first.log") as process:
            dispatch_runs(worker_engine, settings)
            wait_for(lambda: attempts() == 1, process)
        with Session(worker_engine) as db:
            run = db.scalar(select(CheckRun))
            run_id = run.id
            assert run.state == "pending" and run.attempt_count == 1
            assert db.scalar(select(func.count()).select_from(Incident)) == 0
        # No timestamp shortcuts: a restarted real prefork worker waits for persisted due times.
        with worker(worker_engine, settings, tmp_path / "restarted.log") as process:

            def tick_until(predicate):
                end = time.monotonic() + 40
                while time.monotonic() < end:
                    dispatch_runs(worker_engine, settings)
                    if predicate():
                        return
                    assert process.poll() is None
                    time.sleep(0.2)  # Test dispatcher cadence only; probe workers never sleep.
                pytest.fail("The real retry lifecycle did not finish within its test deadline.")

            tick_until(lambda: attempts() == 3)
            with Session(worker_engine) as db:
                incident = db.scalar(select(Incident))
                assert incident is not None and incident.resolved_at is None
                iid = incident.id
                assert db.get(CheckRun, run_id).final_outcome == "failure"
                assert db.get(Monitor, mid).current_state == "down"
                checks = list(
                    db.scalars(
                        select(Check).where(Check.run_id == run_id).order_by(Check.attempt_number)
                    )
                )
                # Durable due times use UTC. WSL suspension can make the fixture's
                # monotonic clock diverge from PostgreSQL and probe wall clocks.
                for previous, current in zip(checks, checks[1:], strict=False):
                    assert current.started_at - previous.finished_at >= timedelta(seconds=9.5)
            assert len(server.hits) == 3
            server.response_status = 200
            server.response_body = b'{"ok":true,"private":"assertion-body-canary"}'
            with Session(worker_engine) as db, db.begin():
                db.get(Monitor, mid).next_due_at = now_utc() - timedelta(seconds=1)
            tick_until(lambda: attempts() == 4)
        with Session(worker_engine) as db:
            incident = db.get(Incident, iid)
            assert incident.resolved_at is not None
            assert incident.opening_evidence["http_status"] == (200 if assertion_failure else 503)
            if assertion_failure:
                assert incident.opening_evidence["error_code"] == "assertion_failed"
                assert incident.confirmation_evidence["assertion_results"][0]["status"] == "failed"
                assert incident.recovery_evidence["assertion_results"][0]["status"] == "passed"
            assert incident.confirmation_evidence["attempt_number"] == 3
            assert incident.recovery_evidence["http_status"] == 200
            assert db.get(Monitor, mid).current_state == "operational"
            assert db.scalar(select(func.count()).select_from(CheckRun)) == 2
        for log in tmp_path.glob("*.log"):
            assert "retry-query-canary" not in log.read_text()
            assert "assertion-body-canary" not in log.read_text()
