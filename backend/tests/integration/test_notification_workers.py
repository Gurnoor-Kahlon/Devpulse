import os
import signal
import time
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import now_utc
from app.models.auth import User
from app.models.monitor import Monitor
from app.models.notification import NotificationChannel, NotificationDelivery
from app.monitoring.runs import claim_run, execute_spec, finish_run
from app.notifications.dispatcher import dispatch_deliveries, publish_delivery
from tests.integration import test_worker_delivery as fixtures
from tests.integration.test_incidents import due, new_run
from tests.integration.test_notifications import retry_now
from tests.integration.test_probes import saved_monitor
from tests.integration.test_worker_delivery import events, wait_for, worker
from tests.probe_fixtures import fixture_server, fixture_settings
from tests.smtp_fixtures import smtp_server

worker_engine = fixtures.worker_engine
worker_settings = fixtures.worker_settings
pytestmark = [pytest.mark.integration, pytest.mark.worker]


def confirmed(engine, server):
    mid = saved_monitor(
        engine, f"http://127.0.0.1:{server.server_port}/controlled?secret=mail-query-canary"
    )
    email = f"notification-{uuid4().hex}@example.com"
    with Session(engine) as db, db.begin():
        user = db.get(User, db.get(Monitor, mid).user_id)
        user.email = email
        db.add(NotificationChannel(user_id=user.id, enabled=True))
    rid = new_run(engine, mid)
    for _ in range(3):
        due(engine, rid)
        spec = claim_run(engine, rid)
        finish_run(engine, spec, execute_spec(spec, fixture_settings(server)))
    with Session(engine) as db:
        did = db.scalar(select(NotificationDelivery.id))
    return mid, email, did


def state(engine, did):
    with Session(engine) as db:
        return db.get(NotificationDelivery, did).status


@pytest.mark.mailpit
def test_real_worker_mailpit_confirmation_recovery_and_duplicate_jobs(
    worker_engine, worker_settings, tmp_path: Path
):
    with fixture_server() as (server, _):
        mid, email, did = confirmed(worker_engine, server)
        for _ in range(3):
            assert publish_delivery(worker_settings, did)
        with worker(
            worker_engine, worker_settings, tmp_path / "mailpit.log", queues="notifications"
        ) as process:
            wait_for(lambda: state(worker_engine, did) == "sent", process)
            server.response_status = 200
            rid = new_run(worker_engine, mid)
            spec = claim_run(worker_engine, rid)
            finish_run(worker_engine, spec, execute_spec(spec, fixture_settings(server)))
            with Session(worker_engine) as db:
                recovered = db.scalar(
                    select(NotificationDelivery.id).where(
                        NotificationDelivery.transition == "resolved"
                    )
                )
            dispatch_deliveries(worker_engine, worker_settings)
            wait_for(lambda: state(worker_engine, recovered) == "sent", process)
        with httpx.Client(
            base_url=os.environ.get("TEST_MAILPIT_URL", "http://127.0.0.1:8025"),
            trust_env=False,
            timeout=5,
        ) as client:
            messages = [
                item
                for item in client.get("/api/v1/messages").json()["messages"]
                if item["To"][0]["Address"] == email
            ]
            assert len(messages) == 2
            assert {item["Subject"] for item in messages} == {
                "DevPulse: incident confirmed",
                "DevPulse: recovery observed",
            }
            for item in messages:
                message = client.get(f"/api/v1/message/{item['ID']}").json()
                assert "/incidents/" in message["Text"] and "/notifications" in message["HTML"]
                assert "mail-query-canary" not in message["Text"]
        with Session(worker_engine) as db:
            assert all(row.attempt_count == 1 for row in db.scalars(select(NotificationDelivery)))
        assert "mail-query-canary" not in (tmp_path / "mailpit.log").read_text()


def test_real_smtp_backoff_survives_worker_restart(worker_engine, worker_settings, tmp_path):
    with fixture_server() as (probe, _), smtp_server() as smtp:
        _, _, did = confirmed(worker_engine, probe)
        smtp.code = 451
        settings = worker_settings.model_copy(update={"smtp_port": smtp.server_address[1]})
        dispatch_deliveries(worker_engine, settings)
        with worker(
            worker_engine, settings, tmp_path / "first.log", queues="notifications"
        ) as process:

            def retried():
                with Session(worker_engine) as db:
                    row = db.get(NotificationDelivery, did)
                    return row.status == "pending" and row.attempt_count == 1

            wait_for(retried, process)
        with Session(worker_engine) as db:
            row = db.get(NotificationDelivery, did)
            assert row.last_error_code == "smtp_rejected" and row.next_attempt_at > now_utc()
            retry_at = row.next_attempt_at
        smtp.code = 250
        with worker(
            worker_engine, settings, tmp_path / "second.log", queues="notifications"
        ) as process:
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline and state(worker_engine, did) != "sent":
                assert process.poll() is None
                dispatch_deliveries(worker_engine, settings)
                time.sleep(0.2)
            assert state(worker_engine, did) == "sent"
        assert len(smtp.accepted) == 1
        # Persisted retries use PostgreSQL UTC, which can move relative to a WSL monotonic clock.
        assert smtp.attempt_wall_times[1] >= retry_at
        with Session(worker_engine) as db:
            assert db.get(NotificationDelivery, did).attempt_count == 2


def test_worker_loss_after_smtp_acceptance_is_reconciled_with_stable_message_id(
    worker_engine, worker_settings, tmp_path
):
    with fixture_server() as (probe, _), smtp_server() as smtp:
        _, _, did = confirmed(worker_engine, probe)
        smtp.pause_ack = True
        settings = worker_settings.model_copy(update={"smtp_port": smtp.server_address[1]})
        log = tmp_path / "loss.log"
        with worker(worker_engine, settings, log, queues="notifications") as process:
            dispatch_deliveries(worker_engine, settings)
            wait_for(lambda: smtp.received.is_set(), process)
            started = events(log, "notification_started")
            assert len(started) == 1
            os.kill(int(started[0]["worker_pid"]), signal.SIGKILL)
            smtp.pause_ack = False
            smtp.release.set()
            retry_now(worker_engine, did, expire=True)
            dispatch_deliveries(worker_engine, settings)
            wait_for(lambda: state(worker_engine, did) == "sent", process)
        assert len(smtp.accepted) == 2  # SMTP acceptance cannot be atomic with our database commit.
        assert smtp.accepted[0]["Message-ID"] == smtp.accepted[1]["Message-ID"]
        with Session(worker_engine) as db:
            assert db.get(NotificationDelivery, did).attempt_count == 2


def test_retention_task_runs_on_real_maintenance_worker(worker_engine, worker_settings, tmp_path):
    from app.jobs.configuration import RETENTION_TASK, create_celery
    from app.models.check import CheckRun
    from app.models.incident import Incident

    with fixture_server() as (probe, _):
        _, _, did = confirmed(worker_engine, probe)
    with Session(worker_engine) as db, db.begin():
        row = db.scalar(select(CheckRun))
        rid = row.id
        row.completed_at = now_utc() - timedelta(days=31)
    app = create_celery(worker_settings)
    try:
        app.send_task(RETENTION_TASK, args=[])
    finally:
        app.close()
    with worker(
        worker_engine, worker_settings, tmp_path / "retention.log", queues="maintenance"
    ) as process:

        def removed():
            with Session(worker_engine) as db:
                return db.get(CheckRun, rid) is None

        wait_for(removed, process)
    with Session(worker_engine) as db:
        incident = db.scalar(select(Incident))
        assert incident.opening_run_id is None and incident.opening_evidence
        assert db.get(NotificationDelivery, did).status == "pending"
