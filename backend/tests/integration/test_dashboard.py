from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.check import Check, CheckRun
from app.models.incident import Incident
from app.services import dashboard
from tests.integration import test_monitors as fixtures

monitor_app = fixtures.monitor_app
client_factory = fixtures.client_factory
pytestmark = pytest.mark.integration
NOW = datetime(2026, 9, 26, 12, 30, tzinfo=UTC)


def run(
    db,
    mid,
    when,
    outcome="success",
    *,
    trigger="scheduled",
    state="completed",
    attempts=1,
    status=200,
    latency=100,
):
    row = CheckRun(monitor_id=mid, scheduled_at=when, configuration_version=1, trigger=trigger)
    db.add(row)
    db.flush()
    row.attempt_count = attempts
    if state != "pending":
        row.state, row.next_attempt_at = state, None
        row.completed_at, row.final_outcome = when + timedelta(seconds=25), outcome
    for attempt in range(1, attempts + 1):
        db.add(
            Check(
                run_id=row.id,
                attempt_number=attempt,
                started_at=when,
                finished_at=when + timedelta(seconds=attempt),
                outcome=(outcome or "failure") if attempt == attempts else "failure",
                http_status=status if attempt == attempts else 503,
                duration_ms=latency if attempt == attempts else 9999,
            )
        )
    return row.id


def test_weighted_runs_final_attempt_latency_exclusions_boundaries_and_gaps(
    client_factory, database_engine, monkeypatch
):
    client, owner = client_factory()
    monkeypatch.setattr(dashboard, "now_utc", lambda: NOW)
    with Session(database_engine) as db:
        a, b = fixtures.seed(db, owner, 2)
        # Monitor A: 1/2 success. Monitor B: 3/3 success. Weighted result is 80%, not 75%.
        run(db, a.id, NOW - timedelta(hours=3), attempts=3, latency=100)
        run(db, a.id, NOW - timedelta(hours=2), "failure", attempts=3, status=None)
        for i in range(3):
            run(db, b.id, NOW - timedelta(minutes=60 + i), latency=300)
        for i, (state, outcome) in enumerate(
            (
                ("cancelled", "failure"),
                ("infrastructure_failed", "infrastructure_failure"),
                ("completed", "blocked"),
                ("pending", None),
            )
        ):
            run(db, a.id, NOW - timedelta(minutes=10 + i), outcome, state=state, status=None)
        run(db, b.id, NOW - timedelta(minutes=20), "failure", trigger="manual")
        run(db, b.id, NOW - timedelta(days=1, microseconds=1), "failure")
        run(db, b.id, NOW, "failure")
        # Start inclusive, end exclusive. Archived history remains in the denominator.
        run(db, b.id, NOW - timedelta(days=1), latency=200)
        b.enabled, b.next_due_at, b.deleted_at = False, None, NOW
        db.commit()
        before = db.scalar(select(func.count()).select_from(CheckRun))
    response = client.get("/api/v1/dashboard")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    data = response.json()
    values = data["metrics"]
    assert values["successful_runs"] == 5 and values["failed_runs"] == 1
    assert values["observations"] == 6 and values["excluded_runs"] == 4
    assert values["uptime_percent"] == pytest.approx(100 * 5 / 6)
    assert values["response_count"] == 5 and values["mean_latency_ms"] == 240
    assert values["first_observation_at"] == (NOW - timedelta(days=1)).isoformat().replace(
        "+00:00", "Z"
    )
    assert sum(bucket["observations"] for bucket in data["buckets"]) == 6
    assert len(data["buckets"]) == 25
    assert data["buckets"][0]["partial"] and data["buckets"][-1]["partial"]
    assert any(bucket["uptime_percent"] is None for bucket in data["buckets"])
    assert data["monitors"]["total"] == 1
    with Session(database_engine) as db:
        assert db.scalar(select(func.count()).select_from(CheckRun)) == before


@pytest.mark.parametrize(
    "window, size, seconds", [("24h", 25, 3600), ("7d", 29, 21600), ("30d", 31, 86400)]
)
def test_empty_windows_are_null_not_perfect_and_contiguous(
    client_factory, monkeypatch, window, size, seconds
):
    client, _ = client_factory(verified=False)
    monkeypatch.setattr(dashboard, "now_utc", lambda: NOW)
    data = client.get("/api/v1/dashboard", params={"window": window}).json()
    assert data["metrics"]["uptime_percent"] is None
    assert data["metrics"]["mean_latency_ms"] is None
    assert data["metrics"]["first_observation_at"] is None
    assert data["monitors"]["total"] == data["open_incidents"] == 0
    assert len(data["buckets"]) == size and data["bucket_seconds"] == seconds
    assert data["buckets"][0]["start"] == data["start"]
    assert data["buckets"][-1]["end"] == data["end"]
    for previous, current in zip(data["buckets"], data["buckets"][1:], strict=False):
        assert previous["end"] == current["start"]


def test_current_states_freshness_and_archived_incidents_are_owned(
    client_factory, database_engine, monkeypatch
):
    client, owner = client_factory()
    other, other_id = client_factory()
    with Session(database_engine) as db:
        rows = fixtures.seed(db, owner, 6)
        for row, state in zip(
            rows,
            ("operational", "down", "confirming_failure", "unknown", "down", "unknown"),
            strict=True,
        ):
            row.current_state, row.updated_at = state, NOW
        rows[0].last_scheduled_check_at = NOW - timedelta(seconds=120)
        rows[1].last_scheduled_check_at = NOW - timedelta(seconds=119)
        rows[4].enabled, rows[4].next_due_at = False, None
        rows[5].enabled, rows[5].next_due_at, rows[5].deleted_at = False, None, NOW
        archived_id = rows[5].id
        db.add(
            Incident(
                monitor_id=archived_id,
                monitor_name="Archived owned incident",
                started_at=NOW - timedelta(days=40),
                confirmed_at=NOW - timedelta(days=40),
                opening_evidence={},
                confirmation_evidence={},
            )
        )
        foreign = fixtures.seed(db, other_id, 1)[0]
        db.add(
            Incident(
                monitor_id=foreign.id,
                monitor_name="Foreign secret",
                started_at=NOW,
                confirmed_at=NOW,
                opening_evidence={},
                confirmation_evidence={},
            )
        )
        db.commit()
    monkeypatch.setattr(dashboard, "now_utc", lambda: NOW)
    data = client.get("/api/v1/dashboard").json()
    assert data["monitors"] == {
        "total": 5,
        "operational": 1,
        "down": 1,
        "confirming_failure": 1,
        "unknown": 1,
        "paused": 1,
        "stale": 1,
        "awaiting_check": 2,
    }
    assert data["open_incidents"] == 1
    assert data["recent_incidents"][0]["monitor_name"] == "Archived owned incident"
    assert "Foreign secret" not in str(data)
    assert other.get("/api/v1/dashboard").json()["monitors"]["total"] == 1


def test_auth_validation_and_pruned_final_check(client_factory, monitor_app, database_engine):
    client, owner = client_factory()
    other, _ = client_factory()
    with Session(database_engine) as db:
        monitor = fixtures.seed(db, owner, 1)[0]
        identifier = run(db, monitor.id, dashboard.now_utc() - timedelta(minutes=1))
        db.flush()
        db.execute(delete(Check).where(Check.run_id == identifier))
        db.commit()
    data = client.get("/api/v1/dashboard").json()
    assert data["metrics"]["observations"] == 1 and data["metrics"]["uptime_percent"] == 100
    assert data["metrics"]["response_count"] == 0 and data["metrics"]["mean_latency_ms"] is None
    assert other.get("/api/v1/dashboard").json()["metrics"]["observations"] == 0
    assert client.get("/api/v1/dashboard?window=365d").status_code == 422
    anonymous = TestClient(monitor_app)
    try:
        assert anonymous.get("/api/v1/dashboard").status_code == 401
    finally:
        anonymous.close()
