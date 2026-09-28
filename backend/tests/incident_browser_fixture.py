"""Opt-in, disposable browser evidence created through real loopback probes."""

from datetime import timedelta

from sqlalchemy import Engine, delete, select
from sqlalchemy.orm import Session

from app.core.security import now_utc, password_hasher
from app.models.assertion import Assertion
from app.models.auth import User
from app.models.check import CheckRun
from app.models.monitor import Monitor
from app.models.notification import NotificationChannel, NotificationDelivery
from app.monitoring.runs import claim_run, create_pending_run, execute_spec, finish_run
from app.notifications.delivery import deliver
from tests.probe_fixtures import fixture_server, fixture_settings


def seed_incident_browser_fixture(
    engine: Engine,
    *,
    retain_monitor_history: bool = False,
    extra_manual_runs: int = 0,
    with_assertions: bool = False,
    with_notifications: bool = False,
) -> None:
    with fixture_server() as (server, _):
        route = "assertion-controlled" if with_assertions else "controlled"
        with Session(engine) as db, db.begin():
            user = User(
                email="incident-browser@example.com",
                password_hash=password_hasher.hash("incident-browser-password"),
                email_verified_at=now_utc(),
            )
            db.add(user)
            db.flush()
            monitor = Monitor(
                user_id=user.id,
                name="Controlled incident fixture",
                url=f"http://127.0.0.1:{server.server_port}/{route}",
                next_due_at=now_utc(),
            )
            db.add(monitor)
            db.flush()
            mid = monitor.id
            if with_notifications:
                db.add(NotificationChannel(user_id=user.id, enabled=True))
            if with_assertions:
                db.add(
                    Assertion(
                        monitor_id=mid, position=0, kind="json_equals", pointer="/ok", expected=True
                    )
                )
        settings = fixture_settings(server)
        # Open, resolve, then open a second incident. Only test retry clocks are accelerated.
        for status, attempts in ((503, 3), (200, 1), (503, 3)):
            server.response_status = status
            server.response_body = (
                b'{"ok":true}' if status == 200 else b'{"ok":false,"private":"browser-body-canary"}'
            )
            identifier = create_pending_run(engine, mid)
            with Session(engine) as db, db.begin():
                db.get(CheckRun, identifier).trigger = "scheduled"
            for _ in range(attempts):
                with Session(engine) as db, db.begin():
                    run = db.get(CheckRun, identifier)
                    run.next_attempt_at = run.next_publish_at = now_utc() - timedelta(seconds=1)
                spec = claim_run(engine, identifier)
                assert spec is not None
                finish_run(engine, spec, execute_spec(spec, settings))
        if with_notifications:
            mail_settings = settings.model_copy(
                update={
                    "smtp_host": "127.0.0.1",
                    "smtp_port": 1025,
                    "smtp_mode": "plain",
                    "smtp_username": None,
                    "smtp_password": None,
                }
            )
            with Session(engine) as db:
                ids = list(
                    db.scalars(
                        select(NotificationDelivery.id).order_by(NotificationDelivery.created_at)
                    )
                )
            for delivery_id in ids:
                deliver(engine, mail_settings, delivery_id)
            with Session(engine) as db:
                assert all(row.status == "sent" for row in db.scalars(select(NotificationDelivery)))
        if retain_monitor_history:
            server.response_status = 200
            for _ in range(extra_manual_runs):
                identifier = create_pending_run(engine, mid)
                spec = claim_run(engine, identifier)
                assert spec is not None
                finish_run(engine, spec, execute_spec(spec, settings))
            return
        # The incident views must remain useful after archive and raw history pruning.
        with Session(engine) as db, db.begin():
            monitor = db.get(Monitor, mid)
            assert monitor is not None
            monitor.enabled, monitor.next_due_at = False, None
            monitor.deleted_at = now_utc()
            db.execute(delete(CheckRun).where(CheckRun.monitor_id == mid))
