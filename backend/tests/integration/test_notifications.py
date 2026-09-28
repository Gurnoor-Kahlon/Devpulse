from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest.mock import Mock
from uuid import UUID

import pytest
from kombu.exceptions import OperationalError as BrokerError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import now_utc
from app.models.auth import User
from app.models.check import Check, CheckRun
from app.models.incident import Incident
from app.models.monitor import Monitor
from app.models.notification import NotificationDelivery
from app.monitoring import incidents
from app.monitoring.runs import claim_run, finish_run
from app.notifications import delivery, dispatcher
from app.notifications.delivery import BACKOFF_SECONDS, claim_delivery, finish_delivery
from app.notifications.outbox import enqueue_transition
from tests.integration import test_monitors as fixtures
from tests.integration.test_incidents import confirm, due, new_run, result

monitor_app = fixtures.monitor_app
client_factory = fixtures.client_factory
pytestmark = pytest.mark.integration
PREFS = "/api/v1/notifications/preferences"
DELIVERIES = "/api/v1/notifications/deliveries"
BODY = {"configuration_version": 0, "enabled": True, "on_open": True, "on_recovery": True}


def setup(client_factory, engine):
    client, uid = client_factory()
    mid = UUID(fixtures.create(client)["id"])
    assert client.put(PREFS, json=BODY).status_code == 200
    iid = confirm(engine, mid)
    with Session(engine) as db:
        did = db.scalar(
            select(NotificationDelivery.id).where(NotificationDelivery.incident_id == iid)
        )
    return client, uid, mid, iid, did


def retry_now(engine, identifier, *, expire=False):
    with Session(engine) as db, db.begin():
        row = db.get(NotificationDelivery, identifier)
        if expire:
            row.lease_expires_at = now_utc() - timedelta(seconds=1)
        else:
            row.next_attempt_at = now_utc() - timedelta(seconds=1)
        row.next_publish_at = now_utc() - timedelta(seconds=1)


def test_default_opt_in_verification_csrf_and_versioned_preferences(
    client_factory, database_engine
):
    client, uid = client_factory(verified=False)
    default = client.get(PREFS).json()
    assert default["configuration_version"] == 0 and default["enabled"] is False
    assert default["verified"] is False
    assert client.put(PREFS, json=BODY).status_code == 403
    with Session(database_engine) as db, db.begin():
        db.get(User, uid).email_verified_at = now_utc()
    token = client.headers.pop("X-CSRF-Token")
    assert client.put(PREFS, json=BODY).status_code == 403
    client.headers["X-CSRF-Token"] = token
    assert (
        client.put(PREFS, json={**BODY, "destination": "arbitrary@example.com"}).status_code == 422
    )
    saved = client.put(PREFS, json=BODY)
    assert saved.status_code == 200 and saved.headers["cache-control"] == "no-store"
    assert saved.json()["configuration_version"] == 1
    assert client.put(PREFS, json=BODY).status_code == 409
    assert client.put(PREFS, json={**BODY, "configuration_version": 1}).json() == saved.json()
    other, _ = client_factory()
    assert other.get(PREFS).json()["enabled"] is False
    assert other.get(DELIVERIES).json()["items"] == []


def test_transactional_transitions_and_delivery_ownership(client_factory, database_engine):
    client, _, mid, iid, did = setup(client_factory, database_engine)
    with Session(database_engine) as db, db.begin():
        enqueue_transition(db, db.get(Monitor, mid), db.get(Incident, iid), "opened")
    assert len(client.get(DELIVERIES).json()["items"]) == 1
    rid = new_run(database_engine, mid)
    finish_run(database_engine, claim_run(database_engine, rid), result("success"))
    response = client.get(DELIVERIES, params={"incident_id": str(iid), "limit": 1}).json()
    assert response["items"][0]["transition"] == "resolved" and response["next_cursor"]
    older = client.get(DELIVERIES, params={"cursor": response["next_cursor"], "limit": 1}).json()
    assert older["items"][0]["id"] == str(did) and older["next_cursor"] is None
    other, _ = client_factory()
    assert other.get(DELIVERIES, params={"incident_id": str(iid)}).status_code == 404
    assert other.get(DELIVERIES).json()["items"] == []
    # Recovery cannot overtake its confirmation delivery.
    recovery_id = UUID(response["items"][0]["id"])
    assert claim_delivery(database_engine, recovery_id) is None
    spec = claim_delivery(database_engine, did)
    assert finish_delivery(database_engine, spec, None)
    assert claim_delivery(database_engine, recovery_id) is not None


def test_incident_and_outbox_rollback_together(client_factory, database_engine, monkeypatch):
    client, _ = client_factory()
    mid = UUID(fixtures.create(client)["id"])
    client.put(PREFS, json=BODY)
    rid = new_run(database_engine, mid)
    for _ in range(2):
        due(database_engine, rid)
        finish_run(database_engine, claim_run(database_engine, rid), result("failure"))
    with Session(database_engine) as db:
        assert db.scalar(select(func.count()).select_from(NotificationDelivery)) == 0
    due(database_engine, rid)
    spec = claim_run(database_engine, rid)
    original = incidents.enqueue_transition

    def fail(*args):
        original(*args)
        raise RuntimeError("fixture rollback")

    monkeypatch.setattr(incidents, "enqueue_transition", fail)
    with pytest.raises(RuntimeError):
        finish_run(database_engine, spec, result("failure"))
    with Session(database_engine) as db:
        assert db.scalar(select(func.count()).select_from(Incident)) == 0
        assert db.scalar(select(func.count()).select_from(NotificationDelivery)) == 0
        assert db.scalar(select(func.count()).select_from(Check)) == 2
    monkeypatch.setattr(incidents, "enqueue_transition", original)
    finish_run(database_engine, spec, result("failure"))
    with Session(database_engine) as db:
        assert db.scalar(select(func.count()).select_from(NotificationDelivery)) == 1


def test_duplicate_claims_expired_leases_and_bounded_retry_budget(client_factory, database_engine):
    _, _, _, _, did = setup(client_factory, database_engine)
    with ThreadPoolExecutor(max_workers=3) as pool:
        specs = list(pool.map(lambda _: claim_delivery(database_engine, did), range(3)))
    old = next(s for s in specs if s)
    assert sum(s is not None for s in specs) == 1
    retry_now(database_engine, did, expire=True)
    assert finish_delivery(database_engine, old, None) is False
    current = claim_delivery(database_engine, did)
    assert current.lease_token != old.lease_token
    assert finish_delivery(database_engine, old, None) is False
    for attempt in range(2, 6):
        assert finish_delivery(database_engine, current, "smtp_unavailable")
        with Session(database_engine) as db:
            row = db.get(NotificationDelivery, did)
            assert row.attempt_count == attempt
            if attempt < 5:
                assert row.status == "pending"
                seconds = (row.next_attempt_at - now_utc()).total_seconds()
                assert BACKOFF_SECONDS[attempt - 1] - 2 < seconds <= BACKOFF_SECONDS[attempt - 1]
            else:
                assert row.status == "failed" and row.completed_at is not None
        assert claim_delivery(database_engine, did) is None
        if attempt < 5:
            retry_now(database_engine, did)
            current = claim_delivery(database_engine, did)


def test_disabling_cancels_queued_and_stops_retries_for_claimed_mail(
    client_factory, database_engine
):
    client, _, mid, _, did = setup(client_factory, database_engine)
    spec = claim_delivery(database_engine, did)
    rid = new_run(database_engine, mid)
    finish_run(database_engine, claim_run(database_engine, rid), result("success"))
    client.put(PREFS, json={**BODY, "configuration_version": 1, "enabled": False})
    client.put(PREFS, json={**BODY, "configuration_version": 2})
    assert finish_delivery(database_engine, spec, "smtp_unavailable")
    items = client.get(DELIVERIES).json()["items"]
    assert {item["status"] for item in items} == {"cancelled"}
    assert all(item["last_error_code"] == "preferences_disabled" for item in items)


def test_no_transaction_during_smtp_and_failure_does_not_change_health(
    client_factory, database_engine, monkeypatch, capsys
):
    _, _, mid, _, did = setup(client_factory, database_engine)

    def unavailable(*args):
        assert database_engine.pool.checkedout() == 0
        raise OSError("smtp-password-canary")

    monkeypatch.setattr(delivery, "send_message", unavailable)
    delivery.deliver(database_engine, Settings(), did)
    with Session(database_engine) as db:
        assert db.get(NotificationDelivery, did).status == "pending"
        assert db.get(NotificationDelivery, did).attempt_count == 1
        assert db.get(Monitor, mid).current_state == "down"
        assert db.scalar(select(CheckRun.final_outcome)) == "failure"
    assert "smtp-password-canary" not in capsys.readouterr().out


def test_lost_publications_are_recoverable_and_broker_failure_is_safe(
    client_factory, database_engine, monkeypatch, capsys
):
    _, _, _, _, did = setup(client_factory, database_engine)
    assert dispatcher.reserve_deliveries(database_engine) == [did]
    assert dispatcher.reserve_deliveries(database_engine) == []
    retry_now(database_engine, did)
    app = Mock()

    def unavailable():
        assert database_engine.pool.checkedout() == 0
        raise BrokerError("redis-password-canary")

    app.connection_for_write.side_effect = unavailable
    monkeypatch.setattr(dispatcher, "create_celery", lambda _: app)
    dispatcher.dispatch_deliveries(database_engine, Settings())
    assert app.close.called
    with Session(database_engine) as db:
        assert db.get(NotificationDelivery, did).status == "pending"
    assert "redis-password-canary" not in capsys.readouterr().out
    retry_now(database_engine, did)
    assert dispatcher.reserve_deliveries(database_engine) == [did]


def test_exhausted_crashed_attempts_do_not_send_a_sixth_time(client_factory, database_engine):
    _, _, _, _, did = setup(client_factory, database_engine)
    for _ in range(5):
        assert claim_delivery(database_engine, did) is not None
        retry_now(database_engine, did, expire=True)
    assert claim_delivery(database_engine, did) is None
    with Session(database_engine) as db:
        row = db.get(NotificationDelivery, did)
        assert row.status == "failed" and row.last_error_code == "delivery_unknown"
        assert row.attempt_count == 5


def test_unverified_address_is_never_claimed(client_factory, database_engine):
    _, uid, _, _, did = setup(client_factory, database_engine)
    with Session(database_engine) as db, db.begin():
        db.get(User, uid).email_verified_at = None
    assert claim_delivery(database_engine, did) is None
    with Session(database_engine) as db:
        assert db.get(NotificationDelivery, did).last_error_code == "email_unverified"
        assert db.get(NotificationDelivery, did).attempt_count == 0


@pytest.mark.parametrize("code", [451, 550])
def test_smtp_rejections_have_safe_bounded_classification(
    client_factory, database_engine, monkeypatch, code
):
    import smtplib

    _, _, _, _, did = setup(client_factory, database_engine)
    monkeypatch.setattr(
        delivery,
        "send_message",
        Mock(side_effect=smtplib.SMTPDataError(code, b"private-smtp-error")),
    )
    delivery.deliver(database_engine, Settings(), did)
    with Session(database_engine) as db:
        row = db.get(NotificationDelivery, did)
        assert row.last_error_code == "smtp_rejected"
        assert row.status == ("pending" if code == 451 else "failed")


def test_disabled_preferences_do_not_backfill_old_incidents(client_factory, database_engine):
    client, _ = client_factory()
    mid = UUID(fixtures.create(client)["id"])
    confirm(database_engine, mid)
    assert client.get(DELIVERIES).json()["items"] == []
    client.put(PREFS, json={**BODY, "on_open": False})
    assert client.get(DELIVERIES).json()["items"] == []
    rid = new_run(database_engine, mid)
    finish_run(database_engine, claim_run(database_engine, rid), result("success"))
    assert [row["transition"] for row in client.get(DELIVERIES).json()["items"]] == ["resolved"]


def test_preferences_race_has_one_winner(client_factory):
    client, uid = client_factory()
    other, _ = client_factory(user_id=uid)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda c: c.put(PREFS, json=BODY), [client, other]))
    assert sorted(r.status_code for r in responses) == [200, 409]


def test_database_failure_after_smtp_keeps_recoverable_lease_and_safe_logs(
    client_factory, database_engine, monkeypatch, capsys
):
    from sqlalchemy.exc import OperationalError

    from app.jobs import tasks

    _, _, mid, _, did = setup(client_factory, database_engine)
    accepted = []
    monkeypatch.setattr(
        delivery, "send_message", lambda settings, message: accepted.append(message["Message-ID"])
    )
    original = delivery.finish_delivery
    monkeypatch.setattr(
        delivery,
        "finish_delivery",
        Mock(
            side_effect=OperationalError(
                "private SQL", {}, RuntimeError("database-password-canary")
            )
        ),
    )
    monkeypatch.setattr(tasks, "create_database_engine", lambda settings: database_engine)
    tasks.notification_job(str(did))
    with Session(database_engine) as db:
        assert db.get(NotificationDelivery, did).status == "sending"
        assert db.get(Monitor, mid).current_state == "down"
    assert "database-password-canary" not in capsys.readouterr().out
    retry_now(database_engine, did, expire=True)
    monkeypatch.setattr(delivery, "finish_delivery", original)
    tasks.notification_job(str(did))
    assert len(accepted) == 2 and accepted[0] == accepted[1]
    with Session(database_engine) as db:
        assert db.get(NotificationDelivery, did).status == "sent"
