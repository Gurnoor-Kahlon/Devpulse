from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.check import Check, CheckRun
from app.services import analytics, monitor_history
from tests.integration import test_monitors as fixtures
from tests.integration.test_dashboard import NOW, run
from tests.integration.test_incidents import confirm

monitor_app = fixtures.monitor_app
client_factory = fixtures.client_factory
pytestmark = pytest.mark.integration


def test_monitor_metrics_scope_final_statuses_exclusions_and_gaps(
    client_factory, database_engine, monkeypatch
):
    client, owner = client_factory()
    monkeypatch.setattr(analytics, "now_utc", lambda: NOW)
    with Session(database_engine) as db:
        a, b = fixtures.seed(db, owner, 2)
        mid = a.id
        run(db, mid, NOW - timedelta(hours=2), attempts=3, latency=100)
        run(db, mid, NOW - timedelta(hours=1), "failure", attempts=3, status=503, latency=200)
        run(db, mid, NOW - timedelta(minutes=50), "failure", status=None)
        run(db, mid, NOW - timedelta(minutes=40), trigger="manual", latency=9999)
        run(db, mid, NOW - timedelta(minutes=30), "blocked", status=403)
        run(db, mid, NOW - timedelta(minutes=20), "failure", state="cancelled", status=502)
        run(db, b.id, NOW - timedelta(minutes=10), latency=9999)
        a.configuration_version = 2
        db.commit()
    response = client.get(f"/api/v1/monitors/{mid}/analytics")
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    data = response.json()
    assert data["metrics"]["uptime_percent"] == pytest.approx(100 / 3)
    assert data["metrics"]["observations"] == 3
    assert data["metrics"]["excluded_runs"] == 2
    assert data["metrics"]["mean_latency_ms"] == 150
    assert data["monitor"]["configuration_version"] == 2
    assert data["status_distribution"] == [
        {"http_status": 200, "count": 1, "percentage": 50},
        {"http_status": 503, "count": 1, "percentage": 50},
    ]
    assert sum(b["observations"] for b in data["buckets"]) == 3
    assert any(b["mean_latency_ms"] is None for b in data["buckets"])


def test_checks_paginate_attempts_with_frozen_window_safe_evidence_and_new_insert(
    client_factory, database_engine, monkeypatch
):
    client, owner = client_factory()
    monkeypatch.setattr(monitor_history, "now_utc", lambda: NOW)
    with Session(database_engine) as db:
        mid = fixtures.seed(db, owner, 1)[0].id
        first = run(db, mid, NOW - timedelta(hours=3), "failure", attempts=3)
        manual = run(db, mid, NOW - timedelta(hours=2), trigger="manual")
        run(db, mid, NOW - timedelta(days=1, seconds=1))
        db.flush()
        for check in db.scalars(select(Check).where(Check.run_id == first)):
            check.error_code = "unexpected_status"
            check.error_message = "secret-header-and-body-canary"
        db.commit()
    path = f"/api/v1/monitors/{mid}/checks"
    first_page = client.get(path, params={"limit": 1}).json()
    assert first_page["items"][0]["trigger"] == "manual"
    assert first_page["items"][0]["run_id"] == str(manual)
    assert first_page["next_cursor"]
    # A later inserted observation lies outside the frozen end even with an older scheduled time.
    with Session(database_engine) as db:
        newer = run(db, mid, NOW - timedelta(minutes=1))
        db.flush()
        db.scalar(select(Check).where(Check.run_id == newer)).finished_at = NOW + timedelta(
            seconds=10
        )
        db.commit()
    cursor, seen, attempts = first_page["next_cursor"], [first_page["items"][0]["id"]], []
    while cursor:
        response = client.get(path, params={"limit": 1, "cursor": cursor})
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        page = response.json()
        assert (page["start"], page["end"]) == (first_page["start"], first_page["end"])
        assert "secret-header-and-body-canary" not in response.text
        for item in page["items"]:
            assert item["run_id"] == str(first)
            assert item["configuration_version"] == 1
            assert item["error_message"] == "The HTTP status did not match the expected status."
            assert item["is_final_attempt"] == (item["attempt_number"] == 3)
            assert not {"url", "headers", "body", "lease_token"}.intersection(item)
            seen.append(item["id"])
            attempts.append(item["attempt_number"])
        cursor = page["next_cursor"]
    assert len(seen) == len(set(seen)) == 4 and attempts == [3, 2, 1]
    for params in (
        {"cursor": "%%%"},
        {"limit": 0},
        {"limit": 101},
        {"window": "year"},
        {"window": "7d", "cursor": first_page["next_cursor"]},
    ):
        assert client.get(path, params=params).status_code == 422


def test_history_auth_archives_incidents_and_pruning(client_factory, database_engine, monitor_app):
    owner, _ = client_factory()
    other, _ = client_factory()
    mid = UUID(str(fixtures.create(owner)["id"]))
    iid = confirm(database_engine, mid)
    for suffix in ("analytics", "checks"):
        path = f"/api/v1/monitors/{mid}/{suffix}"
        assert other.get(path).status_code == 404
        assert owner.get(f"/api/v1/monitors/{uuid4()}/{suffix}").status_code == 404
        anonymous = TestClient(monitor_app)
        try:
            assert anonymous.get(path).status_code == 401
        finally:
            anonymous.close()
    assert owner.delete(f"/api/v1/monitors/{mid}?configuration_version=1").status_code == 204
    data = owner.get(f"/api/v1/monitors/{mid}/analytics").json()
    assert data["archived_at"] and data["metrics"]["failed_runs"] == 1
    assert len(owner.get(f"/api/v1/monitors/{mid}/checks").json()["items"]) == 3
    assert owner.get(f"/api/v1/incidents?monitor_id={mid}").json()["items"][0]["id"] == str(iid)
    with Session(database_engine) as db, db.begin():
        db.execute(delete(CheckRun).where(CheckRun.monitor_id == mid))
    data = owner.get(f"/api/v1/monitors/{mid}/analytics").json()
    assert data["metrics"]["uptime_percent"] is None and data["status_distribution"] == []
    assert owner.get(f"/api/v1/monitors/{mid}/checks").json()["items"] == []
    assert owner.get(f"/api/v1/incidents/{iid}").json()["opening_evidence"]["attempt_number"] == 1


@pytest.mark.parametrize("window", ["24h", "7d", "30d"])
def test_empty_monitor_windows_and_reads_do_not_enqueue(client_factory, database_engine, window):
    client, _ = client_factory()
    mid = fixtures.create(client)["id"]
    data = client.get(f"/api/v1/monitors/{mid}/analytics?window={window}").json()
    assert data["metrics"]["observations"] == 0 and data["metrics"]["mean_latency_ms"] is None
    assert data["status_distribution"] == [] and data["window"] == window
    checks = client.get(f"/api/v1/monitors/{mid}/checks?window={window}").json()
    assert checks["items"] == [] and checks["next_cursor"] is None
    with Session(database_engine) as db:
        assert db.scalar(select(func.count()).select_from(CheckRun)) == 0
