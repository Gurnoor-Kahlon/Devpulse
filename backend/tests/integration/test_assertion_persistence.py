import json
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

import pytest
from sqlalchemy import Engine, delete, select
from sqlalchemy.orm import Session

from app.models.check import Check, CheckRun
from app.models.incident import Incident
from app.models.monitor import Monitor
from app.monitoring.runs import begin_run, claim_run, create_pending_run, execute_spec, finish_run
from tests.integration import test_monitors as fixtures
from tests.integration.test_incidents import due, new_run
from tests.probe_fixtures import fixture_server, fixture_settings

monitor_app = fixtures.monitor_app
client_factory = fixtures.client_factory
pytestmark = pytest.mark.integration
ITEM = {"kind": "json_equals", "pointer": "/ok", "expected": True}


def test_owned_versioned_atomic_assertion_api(client_factory, database_engine: Engine):
    client, _ = client_factory()
    other, _ = client_factory()
    monitor = fixtures.create(client)
    path = f"{fixtures.PREFIX}/{monitor['id']}/assertions"
    assert client.get(path).json()["items"] == []
    body = {"configuration_version": 1, "items": [ITEM]}
    assert other.get(path).status_code == 404
    assert other.put(path, json=body).status_code == 404
    csrf = client.headers.pop("X-CSRF-Token")
    assert client.put(path, json=body).status_code == 403
    client.headers["X-CSRF-Token"] = csrf
    response = client.put(path, json=body)
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["configuration_version"] == 2
    assert response.headers["cache-control"] == "no-store"
    assert client.put(path, json=body).status_code == 409
    assert client.put(path, json={**body, "configuration_version": 2}).json() == saved
    invalid = client.put(
        path,
        json={
            "configuration_version": 2,
            "items": [ITEM, {**ITEM, "pointer": "bad", "expected": "validation-secret-canary"}],
        },
    )
    assert invalid.status_code == 422 and "validation-secret-canary" not in invalid.text
    assert client.get(path).json() == saved
    # True and 1 compare equal in Python but are different JSON types and edits.
    changed = client.put(
        path, json={"configuration_version": 2, "items": [{**ITEM, "expected": 1}]}
    ).json()
    assert changed["configuration_version"] == 3
    assert type(changed["items"][0]["expected"]) is int
    assert changed["items"][0]["id"] != saved["items"][0]["id"]
    with Session(database_engine) as db:
        row = db.get(Monitor, UUID(monitor["id"]))
        assert row.last_scheduled_check_at is None and row.next_due_at is not None
    assert (
        client.patch(
            f"{fixtures.PREFIX}/{monitor['id']}",
            json={"configuration_version": 3, "method": "HEAD"},
        ).status_code
        == 422
    )
    assert (
        client.put(path, json={"configuration_version": 3, "items": []}).json()[
            "configuration_version"
        ]
        == 4
    )
    assert (
        client.patch(
            f"{fixtures.PREFIX}/{monitor['id']}",
            json={"configuration_version": 4, "method": "HEAD"},
        ).status_code
        == 200
    )
    assert client.put(path, json={"configuration_version": 5, "items": [ITEM]}).status_code == 422
    assert client.put(path, json={"configuration_version": 5, "items": []}).status_code == 200
    assert (
        client.delete(f"{fixtures.PREFIX}/{monitor['id']}?configuration_version=5").status_code
        == 204
    )
    assert client.get(path).status_code == 404
    assert client.put(path, json={"configuration_version": 6, "items": []}).status_code == 404


def test_concurrent_writes_have_one_winner(client_factory):
    client, uid = client_factory()
    other, _ = client_factory(user_id=uid)
    monitor = fixtures.create(client)
    path = f"{fixtures.PREFIX}/{monitor['id']}/assertions"
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(
                lambda c: c.put(path, json={"configuration_version": 1, "items": [ITEM]}),
                [client, other],
            )
        )
    assert sorted(r.status_code for r in responses) == [200, 409]


def test_snapshot_survives_edit_and_stale_work_is_cancelled(client_factory, database_engine):
    client, _ = client_factory()
    with fixture_server() as (server, _):
        monitor = fixtures.create(client)
        mid = UUID(monitor["id"])
        # Only fixture setup may target loopback; the public monitor API continues blocking it.
        with Session(database_engine) as db, db.begin():
            db.get(Monitor, mid).url = f"http://127.0.0.1:{server.server_port}/ok"
        path = f"{fixtures.PREFIX}/{mid}/assertions"
        saved = client.put(path, json={"configuration_version": 1, "items": [ITEM]}).json()
        spec = begin_run(database_engine, mid)
        assert spec.assertions[0].id == UUID(saved["items"][0]["id"])
        client.put(path, json={"configuration_version": 2, "items": [{**ITEM, "expected": False}]})
        result = execute_spec(spec, fixture_settings(server))
        check_id = finish_run(database_engine, spec, result)
        assert result.outcome == "success"
        with Session(database_engine) as db:
            assert db.get(CheckRun, spec.run_id).state == "cancelled"
            assert db.get(Check, check_id).assertion_results[0]["definition"]["expected"] is True
            assert db.get(Monitor, mid).last_completed_check_at is None
        queued = create_pending_run(database_engine, mid)
        client.put(path, json={"configuration_version": 3, "items": []})
        assert claim_run(database_engine, queued) is None
        assert len(server.hits) == 1


def test_real_assertion_failures_confirm_recover_and_retain_private_safe_evidence(
    client_factory, database_engine, capsys
):
    client, _ = client_factory()
    with fixture_server() as (server, _):
        monitor = fixtures.create(client)
        mid = UUID(monitor["id"])
        with Session(database_engine) as db, db.begin():
            db.get(
                Monitor, mid
            ).url = f"http://127.0.0.1:{server.server_port}/assertion-controlled?key=query-canary"
        path = f"{fixtures.PREFIX}/{mid}/assertions"
        saved = client.put(path, json={"configuration_version": 1, "items": [ITEM]}).json()
        run_id = new_run(database_engine, mid)
        for attempt in range(3):
            if attempt:
                due(database_engine, run_id)
            spec = claim_run(database_engine, run_id)
            result = execute_spec(spec, fixture_settings(server))
            assert result.http_status == 200 and result.error_code == "assertion_failed"
            finish_run(database_engine, spec, result)
        with Session(database_engine) as db:
            incident = db.scalar(select(Incident))
            iid = incident.id
            assert incident.confirmation_evidence["assertion_results"][0]["status"] == "failed"
            assert db.get(Monitor, mid).current_state == "down"
        server.response_body = b'{"ok":true,"private":"assertion-body-canary"}'
        recovery = new_run(database_engine, mid)
        spec = claim_run(database_engine, recovery)
        finish_run(database_engine, spec, execute_spec(spec, fixture_settings(server)))
        checks = client.get(f"{fixtures.PREFIX}/{mid}/checks").json()["items"]
        assert len(checks) == 4
        assert {r["assertion_results"][0]["status"] for r in checks} == {"failed", "passed"}
        client.put(path, json={"configuration_version": 2, "items": []})
        with Session(database_engine) as db, db.begin():
            db.execute(delete(CheckRun).where(CheckRun.monitor_id == mid))
        detail = client.get(f"/api/v1/incidents/{iid}")
        assert detail.status_code == 200
        evidence = detail.json()
        assert evidence["status"] == "resolved"
        for phase in ("opening_evidence", "confirmation_evidence", "recovery_evidence"):
            assert evidence[phase]["assertion_results"][0]["definition"] == saved["items"][0]
        assert evidence["recovery_evidence"]["assertion_results"][0]["status"] == "passed"
        serialized = json.dumps(checks) + detail.text + capsys.readouterr().out
        assert "assertion-body-canary" not in serialized and "query-canary" not in serialized


def test_json_null_round_trip_and_ten_definition_limit(client_factory):
    client, _ = client_factory()
    monitor = fixtures.create(client)
    path = f"{fixtures.PREFIX}/{monitor['id']}/assertions"
    body = {"configuration_version": 1, "items": [{**ITEM, "expected": None}] * 10}
    response = client.put(path, json=body)
    assert response.status_code == 200
    assert all(item["expected"] is None for item in client.get(path).json()["items"])
    assert (
        client.put(path, json={"configuration_version": 2, "items": [ITEM] * 11}).status_code == 422
    )
    assert len(client.get(path).json()["items"]) == 10


def test_upgrade_preserves_legacy_check_with_empty_snapshot(client_factory, database_engine):
    from pathlib import Path

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect

    from tests.integration.test_probes import success

    client, _ = client_factory()
    monitor = fixtures.create(client)
    spec = begin_run(database_engine, UUID(monitor["id"]))
    cid = finish_run(database_engine, spec, success())
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    with database_engine.connect() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "d93f8b2e015c")
        assert "assertion_results" not in {
            c["name"] for c in inspect(connection).get_columns("checks")
        }
        connection.commit()
        command.upgrade(config, "head")
    with Session(database_engine) as db:
        check = db.get(Check, cid)
        assert check.outcome == "success" and check.assertion_results == []
