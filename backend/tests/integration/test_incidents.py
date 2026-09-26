from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, delete, func, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.core.security import now_utc
from app.jobs.dispatcher import reserve_work
from app.models.check import Check, CheckRun
from app.models.incident import Incident
from app.models.monitor import Monitor
from app.monitoring import runs
from app.monitoring.runs import claim_run, create_pending_run, finish_run
from tests.integration import test_monitors as monitor_fixtures
from tests.integration import test_scheduler as scheduler_fixtures
from tests.integration.test_probes import success

scheduler_engine = scheduler_fixtures.scheduler_engine
monitor_app = monitor_fixtures.monitor_app
client_factory = monitor_fixtures.client_factory
pytestmark = pytest.mark.integration


def new_run(engine: Engine, monitor_id: UUID) -> UUID:
    identifier = create_pending_run(engine, monitor_id)
    with Session(engine) as db, db.begin():
        db.get(CheckRun, identifier).trigger = "scheduled"
    return identifier


def due(engine: Engine, run_id: UUID) -> None:
    with Session(engine) as db, db.begin():
        run = db.get(CheckRun, run_id)
        run.next_attempt_at = run.next_publish_at = now_utc() - timedelta(seconds=1)


def result(outcome: str):
    if outcome == "success":
        return success()
    return replace(
        success(),
        outcome=outcome,
        http_status=503 if outcome == "failure" else None,
        error_code="unexpected_status" if outcome == "failure" else "infrastructure_error",
        error_message="The HTTP status did not match the expected status."
        if outcome == "failure"
        else "Local probe resources are temporarily unavailable.",
    )


def confirm(engine: Engine, monitor_id: UUID) -> UUID:
    identifier = new_run(engine, monitor_id)
    for attempt in range(3):
        if attempt:
            due(engine, identifier)
        spec = claim_run(engine, identifier)
        assert spec is not None
        finish_run(engine, spec, result("failure"))
    with Session(engine) as db:
        return db.scalar(
            select(Incident.id).where(
                Incident.monitor_id == monitor_id, Incident.resolved_at.is_(None)
            )
        )


def test_three_failures_are_durable_delayed_and_confirm_only_once(scheduler_engine: Engine) -> None:
    mid = scheduler_fixtures.monitors(scheduler_engine)[0]
    run_id = new_run(scheduler_engine, mid)
    for attempt in (1, 2):
        spec = claim_run(scheduler_engine, run_id)
        assert spec.attempt_number == attempt
        check_id = finish_run(scheduler_engine, spec, result("failure"))
        assert finish_run(scheduler_engine, spec, result("failure")) is None
        with Session(scheduler_engine) as db:
            run = db.get(CheckRun, run_id)
            now = db.scalar(select(func.clock_timestamp()))
            assert run.state == "pending" and run.attempt_count == attempt
            assert run.completed_at is None and run.final_outcome is None
            assert 8 < (run.next_attempt_at - now).total_seconds() <= 10
            assert run.next_publish_at == run.next_attempt_at and run.lease_token is None
            assert db.get(Check, check_id).attempt_number == attempt
            assert db.get(Monitor, mid).current_state == "confirming_failure"
            assert db.scalar(select(func.count()).select_from(Incident)) == 0
        assert claim_run(scheduler_engine, run_id) is None
        assert reserve_work(scheduler_engine) == []
        due(scheduler_engine, run_id)
    spec = claim_run(scheduler_engine, run_id)
    with ThreadPoolExecutor(max_workers=3) as pool:
        ids = list(
            pool.map(lambda _: finish_run(scheduler_engine, spec, result("failure")), range(3))
        )
    assert sum(value is not None for value in ids) == 1
    with Session(scheduler_engine) as db:
        run = db.get(CheckRun, run_id)
        assert (
            run.state == "completed" and run.final_outcome == "failure" and run.attempt_count == 3
        )
        incident = db.scalar(select(Incident))
        checks = list(db.scalars(select(Check).order_by(Check.attempt_number)))
        assert len(checks) == 3
        assert incident.started_at == checks[0].started_at
        assert incident.confirmed_at >= incident.started_at
        assert incident.opening_check_id == checks[0].id
        assert incident.confirmation_check_id == checks[2].id
        assert incident.opening_evidence["attempt_number"] == 1
        assert incident.confirmation_evidence["attempt_number"] == 3
        assert db.get(Monitor, mid).current_state == "down"
        with pytest.raises(IntegrityError), db.begin_nested():
            db.add(
                Incident(
                    monitor_id=mid,
                    monitor_name="Duplicate",
                    started_at=incident.started_at,
                    confirmed_at=incident.confirmed_at,
                    opening_evidence={},
                    confirmation_evidence={},
                )
            )
            db.flush()


@pytest.mark.parametrize("success_at", [1, 2, 3])
def test_success_ends_the_run_without_opening_an_incident(
    scheduler_engine: Engine, success_at: int
) -> None:
    mid = scheduler_fixtures.monitors(scheduler_engine)[0]
    run_id = new_run(scheduler_engine, mid)
    for attempt in range(1, success_at + 1):
        if attempt > 1:
            due(scheduler_engine, run_id)
        finish_run(
            scheduler_engine,
            claim_run(scheduler_engine, run_id),
            result("success" if attempt == success_at else "failure"),
        )
    with Session(scheduler_engine) as db:
        run = db.get(CheckRun, run_id)
        assert run.state == "completed" and run.final_outcome == "success"
        assert run.attempt_count == success_at and run.next_attempt_at is None
        assert db.scalar(select(func.count()).select_from(Incident)) == 0
        assert db.get(Monitor, mid).current_state == "operational"


def test_existing_incident_stays_open_until_one_success_and_can_reopen(
    scheduler_engine: Engine,
) -> None:
    mid = scheduler_fixtures.monitors(scheduler_engine)[0]
    iid = confirm(scheduler_engine, mid)
    assert confirm(scheduler_engine, mid) == iid
    run_id = new_run(scheduler_engine, mid)
    finish_run(scheduler_engine, claim_run(scheduler_engine, run_id), result("failure"))
    with Session(scheduler_engine) as db:
        assert db.get(Monitor, mid).current_state == "down"
    due(scheduler_engine, run_id)
    spec = claim_run(scheduler_engine, run_id)
    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(lambda _: finish_run(scheduler_engine, spec, success()), range(2)))
    assert sum(value is not None for value in ids) == 1
    with Session(scheduler_engine) as db:
        incident = db.get(Incident, iid)
        assert incident.resolved_at >= incident.confirmed_at
        assert incident.recovery_run_id == run_id
        assert incident.recovery_evidence["attempt_number"] == 2
        assert incident.recovery_evidence["outcome"] == "success"
        assert db.get(Monitor, mid).current_state == "operational"
    assert confirm(scheduler_engine, mid) != iid


@pytest.mark.parametrize("outcome", ["blocked", "infrastructure_failure"])
def test_infrastructure_and_blocked_results_neither_confirm_nor_resolve(
    scheduler_engine: Engine, outcome: str
) -> None:
    mid = scheduler_fixtures.monitors(scheduler_engine)[0]
    run_id = new_run(scheduler_engine, mid)
    finish_run(scheduler_engine, claim_run(scheduler_engine, run_id), result("failure"))
    due(scheduler_engine, run_id)
    finish_run(scheduler_engine, claim_run(scheduler_engine, run_id), result(outcome))
    with Session(scheduler_engine) as db:
        assert db.get(Monitor, mid).current_state == "unknown"
        assert db.scalar(select(func.count()).select_from(Incident)) == 0
    iid = confirm(scheduler_engine, mid)
    next_run = new_run(scheduler_engine, mid)
    finish_run(scheduler_engine, claim_run(scheduler_engine, next_run), result(outcome))
    with Session(scheduler_engine) as db:
        assert db.get(Incident, iid).resolved_at is None
        assert db.get(Monitor, mid).current_state == "down"


def test_manual_observations_do_not_retry_or_change_incidents(scheduler_engine: Engine) -> None:
    mid = scheduler_fixtures.monitors(scheduler_engine)[0]
    manual = create_pending_run(scheduler_engine, mid)
    finish_run(scheduler_engine, claim_run(scheduler_engine, manual), result("failure"))
    with Session(scheduler_engine) as db:
        assert db.get(CheckRun, manual).state == "completed"
        assert db.get(Monitor, mid).current_state == "unknown"
    iid = confirm(scheduler_engine, mid)
    manual = create_pending_run(scheduler_engine, mid)
    finish_run(scheduler_engine, claim_run(scheduler_engine, manual), success())
    with Session(scheduler_engine) as db:
        assert db.get(Incident, iid).resolved_at is None
        assert db.get(Monitor, mid).current_state == "down"


@pytest.mark.parametrize("change", ["pause", "archive", "edit"])
def test_configuration_changes_cancel_retries_without_false_recovery(
    scheduler_engine: Engine, change: str
) -> None:
    mid = scheduler_fixtures.monitors(scheduler_engine)[0]
    iid = confirm(scheduler_engine, mid)
    run_id = new_run(scheduler_engine, mid)
    finish_run(scheduler_engine, claim_run(scheduler_engine, run_id), result("failure"))
    due(scheduler_engine, run_id)
    with Session(scheduler_engine) as db, db.begin():
        monitor = db.get(Monitor, mid)
        monitor.configuration_version += 1
        if change != "edit":
            monitor.enabled, monitor.next_due_at = False, None
        if change == "archive":
            monitor.deleted_at = now_utc()
    assert claim_run(scheduler_engine, run_id) is None
    with Session(scheduler_engine) as db:
        assert db.get(CheckRun, run_id).state == "cancelled"
        assert db.get(Incident, iid).resolved_at is None
        assert db.get(Monitor, mid).current_state == "down"


def test_retry_window_allows_continuation_but_rejects_abandoned_old_runs(
    scheduler_engine: Engine,
) -> None:
    mid = scheduler_fixtures.monitors(scheduler_engine)[0]
    run_id = new_run(scheduler_engine, mid)
    finish_run(scheduler_engine, claim_run(scheduler_engine, run_id), result("failure"))
    due(scheduler_engine, run_id)
    with Session(scheduler_engine) as db, db.begin():
        db.get(CheckRun, run_id).scheduled_at = now_utc() - timedelta(seconds=70)
    spec = claim_run(scheduler_engine, run_id)
    assert spec.attempt_number == 2
    finish_run(scheduler_engine, spec, result("failure"))
    due(scheduler_engine, run_id)
    with Session(scheduler_engine) as db, db.begin():
        db.get(CheckRun, run_id).scheduled_at = now_utc() - timedelta(seconds=181)
    assert claim_run(scheduler_engine, run_id) is None
    with Session(scheduler_engine) as db:
        assert db.get(Monitor, mid).current_state == "unknown"
        assert db.scalar(select(func.count()).select_from(Incident)) == 0


def test_incident_and_attempt_are_atomic_on_database_failure(
    scheduler_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    mid = scheduler_fixtures.monitors(scheduler_engine)[0]
    run_id = new_run(scheduler_engine, mid)
    for _ in range(2):
        finish_run(scheduler_engine, claim_run(scheduler_engine, run_id), result("failure"))
        due(scheduler_engine, run_id)
    spec = claim_run(scheduler_engine, run_id)
    original = runs.apply_observation

    def unavailable(db, monitor, run, check):
        original(db, monitor, run, check)
        db.flush()
        raise OperationalError("", {}, Exception())

    with monkeypatch.context() as patch:
        patch.setattr(runs, "apply_observation", unavailable)
        with pytest.raises(OperationalError):
            finish_run(scheduler_engine, spec, result("failure"))
    with Session(scheduler_engine) as db:
        assert db.get(CheckRun, run_id).attempt_count == 2
        assert db.scalar(select(func.count()).select_from(Check)) == 2
        assert db.scalar(select(func.count()).select_from(Incident)) == 0
        assert db.get(Monitor, mid).current_state == "confirming_failure"
    finish_run(scheduler_engine, spec, result("failure"))
    with Session(scheduler_engine) as db:
        assert db.scalar(select(func.count()).select_from(Incident)) == 1


def test_incident_api_ownership_pagination_and_retained_evidence(
    client_factory, database_engine: Engine, capsys
) -> None:
    owner, _ = client_factory()
    other, _ = client_factory()
    mid = UUID(
        monitor_fixtures.create(owner, url="https://example.com/?token=incident-query-canary")["id"]
    )
    ids = []
    for _ in range(3):
        ids.append(confirm(database_engine, mid))
        run_id = new_run(database_engine, mid)
        finish_run(database_engine, claim_run(database_engine, run_id), success())
    iid = confirm(database_engine, mid)
    ids.append(iid)
    assert other.get("/api/v1/incidents").json()["items"] == []
    assert other.get(f"/api/v1/incidents/{iid}").status_code == 404
    assert other.get("/api/v1/incidents", params={"monitor_id": str(mid)}).status_code == 404
    anonymous = TestClient(owner.app)
    try:
        assert anonymous.get("/api/v1/incidents").status_code == 401
    finally:
        anonymous.close()
    received, cursor = [], None
    while True:
        response = owner.get(
            "/api/v1/incidents", params={"limit": 1, **({"cursor": cursor} if cursor else {})}
        )
        assert response.headers["cache-control"] == "no-store"
        assert response.status_code == 200
        page = response.json()
        received.extend(row["id"] for row in page["items"])
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert len(received) == len(set(received)) == 4
    assert set(received) == {str(value) for value in ids}
    assert len(owner.get("/api/v1/incidents", params={"status": "open"}).json()["items"]) == 1
    assert len(owner.get("/api/v1/incidents", params={"status": "resolved"}).json()["items"]) == 3
    for params in ({"limit": 101}, {"limit": 0}, {"cursor": "%%%"}, {"status": "fake"}):
        assert owner.get("/api/v1/incidents", params=params).status_code == 422
    detail = owner.get(f"/api/v1/incidents/{ids[0]}").json()
    assert detail["opening_evidence"]["http_status"] == 503
    assert detail["recovery_evidence"]["outcome"] == "success"
    assert "incident-query-canary" not in str(detail)
    assert (
        owner.delete(f"/api/v1/monitors/{mid}", params={"configuration_version": 1}).status_code
        == 204
    )
    with Session(database_engine) as db, db.begin():
        db.execute(delete(CheckRun).where(CheckRun.monitor_id == mid))
    retained = owner.get(f"/api/v1/incidents/{ids[0]}").json()
    assert retained["opening_check_id"] is None and retained["recovery_run_id"] is None
    assert retained["opening_evidence"] == detail["opening_evidence"]
    assert retained["confirmation_evidence"] == detail["confirmation_evidence"]
    assert retained["recovery_evidence"] == detail["recovery_evidence"]
    assert len(owner.get("/api/v1/incidents", params={"monitor_id": str(mid)}).json()["items"]) == 4
    assert owner.get(f"/api/v1/incidents/{iid}").json()["status"] == "open"
    assert "incident-query-canary" not in capsys.readouterr().out


def test_expired_retry_lease_reuses_attempt_number_and_fences_old_completion(
    scheduler_engine: Engine,
) -> None:
    mid = scheduler_fixtures.monitors(scheduler_engine)[0]
    run_id = new_run(scheduler_engine, mid)
    finish_run(scheduler_engine, claim_run(scheduler_engine, run_id), result("failure"))
    due(scheduler_engine, run_id)
    old = claim_run(scheduler_engine, run_id)
    with Session(scheduler_engine) as db, db.begin():
        db.get(CheckRun, run_id).lease_expires_at = now_utc() - timedelta(seconds=1)
    current = claim_run(scheduler_engine, run_id)
    assert old.attempt_number == current.attempt_number == 2
    assert finish_run(scheduler_engine, old, result("failure")) is None
    finish_run(scheduler_engine, current, success())
    with Session(scheduler_engine) as db:
        assert db.scalar(select(func.count()).select_from(Check)) == 2
        assert db.get(CheckRun, run_id).final_outcome == "success"
        assert db.scalar(select(func.count()).select_from(Incident)) == 0


def test_retry_migration_backfills_existing_attempts_without_inventing_incidents(
    scheduler_engine: Engine,
) -> None:
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    mid = scheduler_fixtures.monitors(scheduler_engine)[0]
    run_id = create_pending_run(scheduler_engine, mid)
    finish_run(scheduler_engine, claim_run(scheduler_engine, run_id), success())
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    with scheduler_engine.connect() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "c82e7a1d904b")
        command.upgrade(config, "head")
        command.check(config)
    with Session(scheduler_engine) as db:
        assert db.get(CheckRun, run_id).attempt_count == 1
        assert db.scalar(select(func.count()).select_from(Check)) == 1
        assert db.scalar(select(func.count()).select_from(Incident)) == 0
