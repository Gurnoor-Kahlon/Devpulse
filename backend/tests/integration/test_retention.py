from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import now_utc
from app.jobs import retention
from app.models.auth import AuthSession, AuthToken, RateLimitBucket
from app.models.check import Check, CheckRun
from app.models.incident import Incident
from app.models.monitor import Monitor
from app.models.notification import NotificationDelivery
from app.monitoring.runs import claim_run, create_pending_run, finish_run
from app.notifications.delivery import claim_delivery, finish_delivery
from tests.integration import test_monitors as fixtures
from tests.integration.test_incidents import new_run, result
from tests.integration.test_notifications import setup

monitor_app = fixtures.monitor_app
client_factory = fixtures.client_factory
pytestmark = pytest.mark.integration


def test_raw_retention_is_bounded_skips_locks_and_preserves_evidence(
    client_factory, database_engine, monkeypatch
):
    _, _, mid, iid, did = setup(client_factory, database_engine)
    spec = claim_delivery(database_engine, did)
    finish_delivery(database_engine, spec, None)
    rid = new_run(database_engine, mid)
    finish_run(database_engine, claim_run(database_engine, rid), result("success"))
    with Session(database_engine) as db, db.begin():
        incident = db.get(Incident, iid)
        before = (
            incident.opening_evidence,
            incident.confirmation_evidence,
            incident.recovery_evidence,
        )
        for run in db.scalars(select(CheckRun)):
            run.completed_at = now_utc() - timedelta(days=31)
        old_ids = list(db.scalars(select(CheckRun.id)))
    pending = create_pending_run(database_engine, mid)
    with Session(database_engine) as db, db.begin():
        db.get(CheckRun, pending).scheduled_at = now_utc() - timedelta(days=40)
    monkeypatch.setattr(retention, "BATCH_SIZE", 1)
    with Session(database_engine) as locked, locked.begin():
        locked.scalar(select(Monitor).where(Monitor.id == mid).with_for_update())
        retention.prune_history(database_engine)
        with Session(database_engine) as db:
            assert db.scalar(select(func.count()).select_from(CheckRun)) == 3
            assert db.get(CheckRun, old_ids[0]) is not None
    retention.prune_history(database_engine)
    with Session(database_engine) as db:
        assert db.scalar(select(func.count()).select_from(CheckRun)) == 2
    retention.prune_history(database_engine)
    with Session(database_engine) as db:
        assert db.scalar(select(func.count()).select_from(CheckRun)) == 1
        assert db.get(CheckRun, pending).state == "pending"
        assert db.scalar(select(func.count()).select_from(Check)) == 0
        incident = db.get(Incident, iid)
        assert (
            incident.opening_evidence,
            incident.confirmation_evidence,
            incident.recovery_evidence,
        ) == before
        assert (
            incident.opening_run_id is incident.opening_check_id is incident.recovery_run_id is None
        )
        assert db.get(NotificationDelivery, did).status == "sent"


def test_recent_history_active_auth_and_rate_limits_are_preserved(client_factory, database_engine):
    _, uid, _, _, _ = setup(client_factory, database_engine)
    now = now_utc()
    with Session(database_engine) as db, db.begin():
        old_session = AuthSession(
            user_id=uid,
            token_hash=uuid4().hex,
            csrf_token_hash=uuid4().hex,
            created_at=now - timedelta(days=3),
            last_activity_at=now - timedelta(days=2),
            expires_at=now + timedelta(days=1),
        )
        live_session = AuthSession(
            user_id=uid,
            token_hash=uuid4().hex,
            csrf_token_hash=uuid4().hex,
            created_at=now,
            last_activity_at=now,
            expires_at=now + timedelta(days=1),
        )
        expired = AuthToken(
            user_id=uid,
            purpose="verification",
            token_hash=uuid4().hex,
            created_at=now - timedelta(days=3),
            expires_at=now - timedelta(days=2),
        )
        live = AuthToken(
            user_id=uid,
            purpose="verification",
            token_hash=uuid4().hex,
            created_at=now,
            expires_at=now + timedelta(hours=1),
        )
        consumed = AuthToken(
            user_id=uid,
            purpose="reset",
            token_hash=uuid4().hex,
            created_at=now - timedelta(days=2),
            consumed_at=now - timedelta(days=2),
            expires_at=now + timedelta(hours=1),
        )
        db.add_all(
            [
                old_session,
                live_session,
                expired,
                live,
                consumed,
                RateLimitBucket(
                    scope_hash="expired", counter=1, expires_at=now - timedelta(seconds=1)
                ),
                RateLimitBucket(scope_hash="live", counter=1, expires_at=now + timedelta(hours=1)),
            ]
        )
        db.flush()
        ids = [r.id for r in (old_session, live_session, expired, live, consumed)]
    retention.prune_history(database_engine)
    with Session(database_engine) as db:
        assert db.get(AuthSession, ids[0]) is None and db.get(AuthSession, ids[1]) is not None
        assert db.get(AuthToken, ids[2]) is None and db.get(AuthToken, ids[3]) is not None
        assert db.get(AuthToken, ids[4]) is None
        assert db.get(RateLimitBucket, "expired") is None
        assert db.get(RateLimitBucket, "live") is not None
        assert db.scalar(select(func.count()).select_from(Check)) == 3
