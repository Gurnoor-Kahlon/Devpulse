import asyncio
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.logging import configure_logging
from app.core.security import now_utc
from app.models.auth import User
from app.models.check import Check, CheckRun
from app.models.monitor import Monitor
from app.monitoring import cli
from app.monitoring.executor import ProbeResult, execute_probe
from app.monitoring.runs import RunError, begin_run, finish_run, run_monitor
from tests.probe_fixtures import fixture_server, fixture_settings

pytestmark = pytest.mark.integration


@pytest.fixture
def probe_engine(database_engine: Engine) -> Engine:
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    with database_engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    return database_engine


def saved_monitor(engine: Engine, url: str) -> UUID:
    with Session(engine) as db:
        user = User(email="probe@example.com", password_hash="unused", email_verified_at=now_utc())
        db.add(user)
        db.flush()
        monitor = Monitor(user_id=user.id, name="Probe fixture", url=url, next_due_at=now_utc())
        db.add(monitor)
        db.commit()
        return monitor.id


def success() -> ProbeResult:
    now = now_utc()
    return ProbeResult(now, now, 12.5, "success", 200, None, None)


def test_operator_command_runs_real_http_and_persists_safe_results(
    probe_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with fixture_server() as (server, _):
        identifier = saved_monitor(
            probe_engine, f"http://127.0.0.1:{server.server_port}/json?key=private-query-canary"
        )
        monkeypatch.setattr(cli, "load_settings", lambda: fixture_settings(server))
        monkeypatch.setattr(cli, "create_database_engine", lambda settings: probe_engine)
        monkeypatch.setattr(sys, "argv", ["probe", str(identifier)])
        assert cli.main() == 0
        output = capsys.readouterr().out
        assert "private-query-canary" not in output and "response-secret-canary" not in output
        report = json.loads(output.splitlines()[-1])
        assert report["outcome"] == "success" and report["http_status"] == 200
        with Session(probe_engine) as db:
            check = db.get(Check, UUID(report["check_id"]))
            run = db.get(CheckRun, UUID(report["run_id"]))
            assert check.run_id == run.id and run.trigger == "manual"
            assert run.state == "completed" and run.final_outcome == "success"
            assert db.get(Monitor, identifier).last_completed_check_at == check.finished_at
            assert db.get(Monitor, identifier).current_state == "unknown"
            assert check.error_message is None and check.attempt_number == 1
            assert "body" not in Check.__table__.columns


def test_no_database_session_is_held_during_dns_or_http(probe_engine: Engine) -> None:
    with fixture_server() as (server, _):
        identifier = saved_monitor(probe_engine, f"http://probe.test:{server.server_port}/ok")
        spec = begin_run(probe_engine, identifier)

        async def resolver(host: str, port: int) -> list[str]:
            assert probe_engine.pool.checkedout() == 0
            return ["127.0.0.1"]

        result = asyncio.run(
            execute_probe(
                spec.url,
                spec.method,
                spec.expected_status,
                spec.timeout_seconds,
                fixture_settings(server, "probe.test"),
                resolver=resolver,
            )
        )
        assert result.outcome == "success"
        assert finish_run(probe_engine, spec, result) is not None


@pytest.mark.parametrize("change", ["edit", "pause", "archive"])
def test_outdated_or_disabled_runs_retain_attempt_but_do_not_change_current_state(
    probe_engine: Engine, change: str
) -> None:
    identifier = saved_monitor(probe_engine, "https://example.com/")
    spec = begin_run(probe_engine, identifier)
    with Session(probe_engine) as db:
        monitor = db.get(Monitor, identifier)
        monitor.configuration_version += 1
        if change in {"pause", "archive"}:
            monitor.enabled = False
            monitor.next_due_at = None
        if change == "archive":
            monitor.deleted_at = now_utc()
        db.commit()
    check_id = finish_run(probe_engine, spec, success())
    with Session(probe_engine) as db:
        assert db.get(Check, check_id).outcome == "success"
        assert db.get(CheckRun, spec.run_id).state == "cancelled"
        monitor = db.get(Monitor, identifier)
        assert monitor.current_state == "unknown" and monitor.last_completed_check_at is None


def test_concurrent_operator_runs_and_duplicate_completion_are_deduplicated(
    probe_engine: Engine,
) -> None:
    identifier = saved_monitor(probe_engine, "https://example.com/")

    def start() -> object:
        try:
            return begin_run(probe_engine, identifier)
        except RunError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        specs = list(pool.map(lambda _: start(), range(2)))
    assert sum(spec is not None for spec in specs) == 1
    spec = next(spec for spec in specs if spec is not None)
    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(lambda _: finish_run(probe_engine, spec, success()), range(2)))
    assert sum(identifier is not None for identifier in ids) == 1
    with Session(probe_engine) as db:
        assert db.scalar(select(func.count()).select_from(Check)) == 1
        assert db.scalar(select(func.count()).select_from(CheckRun)) == 1


def test_database_constraints_enforce_active_run_and_attempt_uniqueness(
    probe_engine: Engine,
) -> None:
    identifier = saved_monitor(probe_engine, "https://example.com/")
    spec = begin_run(probe_engine, identifier)
    with Session(probe_engine) as db:
        with pytest.raises(IntegrityError), db.begin_nested():
            db.add(CheckRun(monitor_id=identifier, scheduled_at=now_utc(), configuration_version=1))
            db.flush()
    check_id = finish_run(probe_engine, spec, success())
    with Session(probe_engine) as db:
        check = db.get(Check, check_id)
        with pytest.raises(IntegrityError), db.begin_nested():
            db.add(
                Check(
                    run_id=spec.run_id,
                    attempt_number=1,
                    started_at=check.started_at,
                    finished_at=check.finished_at,
                    duration_ms=1,
                    outcome="success",
                    http_status=200,
                )
            )
            db.flush()


def test_blocked_and_infrastructure_results_never_mark_target_down(probe_engine: Engine) -> None:
    identifier = saved_monitor(probe_engine, "http://169.254.169.254/latest/meta-data/")
    from app.core.config import Settings

    _, _, result = run_monitor(probe_engine, Settings(environment="test"), identifier)
    assert result.outcome == "blocked"
    spec = begin_run(probe_engine, identifier)
    finish_run(
        probe_engine,
        spec,
        replace(
            success(),
            outcome="infrastructure_failure",
            http_status=None,
            error_code="infrastructure_error",
            error_message="Local probe resources are temporarily unavailable.",
        ),
    )
    with Session(probe_engine) as db:
        assert db.get(CheckRun, spec.run_id).state == "infrastructure_failed"
        assert db.get(Monitor, identifier).last_completed_check_at is None
        assert db.get(Monitor, identifier).current_state == "unknown"


def test_paused_and_unverified_monitors_do_not_create_runs(probe_engine: Engine) -> None:
    identifier = saved_monitor(probe_engine, "https://example.com/")
    with Session(probe_engine) as db:
        monitor = db.get(Monitor, identifier)
        monitor.enabled = False
        monitor.next_due_at = None
        db.commit()
    with pytest.raises(RunError):
        begin_run(probe_engine, identifier)
    with Session(probe_engine) as db:
        monitor = db.get(Monitor, identifier)
        monitor.enabled = True
        monitor.next_due_at = now_utc()
        db.get(User, monitor.user_id).email_verified_at = None
        db.commit()
    with pytest.raises(RunError):
        begin_run(probe_engine, identifier)
    with Session(probe_engine) as db:
        assert db.scalar(select(func.count()).select_from(CheckRun)) == 0


def test_probe_logging_does_not_expose_query_headers_or_bodies(
    probe_engine: Engine, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging("DEBUG")
    with fixture_server() as (server, _):
        identifier = saved_monitor(
            probe_engine, f"http://127.0.0.1:{server.server_port}/json?token=query-secret-canary"
        )
        run_id, _, _ = run_monitor(probe_engine, fixture_settings(server), identifier)
        output = capsys.readouterr().out
        assert str(run_id) in output and "probe_completed" in output
        assert "query-secret-canary" not in output and "response-secret-canary" not in output
