from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import DemoPublication
from app.core.security import now_utc
from app.models.auth import User
from app.models.check import CheckRun
from app.models.incident import Incident
from app.models.monitor import Monitor
from tests.incident_browser_fixture import seed_incident_browser_fixture
from tests.integration import test_monitors as fixtures
from tests.integration.test_dashboard import run

monitor_app = fixtures.monitor_app
client_factory = fixtures.client_factory
pytestmark = pytest.mark.integration


def publish(app, owner, mid, **changes):
    item = DemoPublication(
        owner_id=owner,
        monitor_id=mid,
        configuration_version=1,
        slug="controlled",
        label="Published exercise",
        controlled_failure=True,
    ).model_copy(update=changes)
    app.state.settings = app.state.settings.model_copy(update={"demo_publications": (item,)})


def test_default_empty_read_only_and_bounded(monitor_app):
    client = TestClient(monitor_app)
    try:
        response = client.get("/api/v1/demo")
        assert response.status_code == 200
        assert response.json()["monitors"] == []
        assert response.headers["cache-control"] == "no-store"
        assert "set-cookie" not in response.headers
        assert client.get("/api/v1/demo?window=365d").status_code == 422
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            assert client.request(method, "/api/v1/demo", json={}).status_code == 405
        assert client.get("/api/v1/demo/arbitrary-id").status_code == 404
        assert client.get("/api/v1/monitors").status_code == 401
    finally:
        client.close()


def test_only_explicit_monitor_and_restricted_fields_are_public(
    client_factory, monitor_app, database_engine, capsys
):
    _, owner = client_factory()
    _, stranger = client_factory()
    with Session(database_engine) as db:
        published, private = fixtures.seed(db, owner, 2)
        foreign = fixtures.seed(db, stranger, 1)[0]
        published.name = "private-name-canary"
        published.url = "https://example.com/?secret=private-url-canary"
        now = now_utc()
        run(db, published.id, now - timedelta(minutes=2), attempts=3)
        run(db, published.id, now - timedelta(minutes=1), "failure", attempts=3, status=503)
        run(db, private.id, now - timedelta(minutes=1))
        run(db, foreign.id, now - timedelta(minutes=1))
        db.add(
            Incident(
                monitor_id=published.id,
                monitor_name="incident-name-canary",
                started_at=now,
                confirmed_at=now,
                opening_evidence={"private": "assertion-canary"},
                confirmation_evidence={"private": "body-canary"},
            )
        )
        mid, hidden, other = published.id, private.id, foreign.id
        published.last_scheduled_check_at = now - timedelta(minutes=5)
        db.commit()
        before = db.scalar(select(func.count()).select_from(CheckRun))
    publish(monitor_app, owner, mid)
    client = TestClient(monitor_app)
    try:
        response = client.get(f"/api/v1/demo?monitor_id={hidden}&owner_id={stranger}")
        data = response.json()
        assert set(data) == {"generated_at", "monitors"}
        assert len(data["monitors"]) == 1
        item = data["monitors"][0]
        assert set(item) == {
            "slug",
            "label",
            "controlled_failure",
            "state",
            "stale",
            "last_checked_at",
            "history",
            "recent_incidents",
        }
        assert item["history"]["metrics"]["observations"] == 2
        assert item["history"]["metrics"]["uptime_percent"] == 50
        assert item["stale"] and item["controlled_failure"]
        assert set(item["recent_incidents"][0]) == {
            "started_at",
            "confirmed_at",
            "resolved_at",
        }
        output = response.text + capsys.readouterr().out
        for secret in (
            "private-name-canary",
            "private-url-canary",
            "incident-name-canary",
            "assertion-canary",
            "body-canary",
            str(mid),
            str(hidden),
            str(other),
            str(owner),
        ):
            assert secret not in output
        for window in ("24h", "7d", "30d"):
            assert client.get(f"/api/v1/demo?window={window}").status_code == 200
        with Session(database_engine) as db:
            assert db.scalar(select(func.count()).select_from(CheckRun)) == before
    finally:
        client.close()


@pytest.mark.parametrize("reason", ["owner", "version", "archive", "unverified", "removed"])
def test_publication_fails_closed_and_revocation_removes_history(
    client_factory, monitor_app, database_engine, reason
):
    _, owner = client_factory()
    with Session(database_engine) as db:
        monitor = fixtures.seed(db, owner, 1)[0]
        mid = monitor.id
    publish(monitor_app, owner, mid)
    client = TestClient(monitor_app)
    try:
        assert len(client.get("/api/v1/demo").json()["monitors"]) == 1
        with Session(database_engine) as db:
            monitor = db.get(Monitor, mid)
            if reason == "owner":
                publish(monitor_app, uuid4(), mid)
            elif reason == "version":
                monitor.configuration_version += 1
            elif reason == "archive":
                monitor.enabled, monitor.next_due_at, monitor.deleted_at = False, None, now_utc()
            elif reason == "unverified":
                db.get(User, owner).email_verified_at = None
            else:
                monitor_app.state.settings = monitor_app.state.settings.model_copy(
                    update={"demo_publications": ()}
                )
            db.commit()
        assert client.get("/api/v1/demo").json()["monitors"] == []
    finally:
        client.close()


def test_real_probe_pipeline_supplies_public_metrics_and_incident_times(
    monitor_app, database_engine
):
    seed_incident_browser_fixture(database_engine, retain_monitor_history=True)
    with Session(database_engine) as db:
        monitor = db.scalar(select(Monitor))
        publish(monitor_app, monitor.user_id, monitor.id)
    client = TestClient(monitor_app)
    try:
        item = client.get("/api/v1/demo").json()["monitors"][0]
        metrics = item["history"]["metrics"]
        assert metrics["observations"] == 3
        assert metrics["successful_runs"] == 1 and metrics["failed_runs"] == 2
        assert metrics["uptime_percent"] == pytest.approx(100 / 3)
        assert metrics["response_count"] == 3
        assert metrics["mean_latency_ms"] > 0
        assert item["state"] == "down"
        assert len(item["recent_incidents"]) == 2
        assert item["recent_incidents"][0]["resolved_at"] is None
        assert item["recent_incidents"][1]["resolved_at"] is not None
    finally:
        client.close()
