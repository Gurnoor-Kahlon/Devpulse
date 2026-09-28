"""Bounded cleanup; incident evidence and notification status are retained."""

from datetime import timedelta

from sqlalchemy import Engine, delete, func, or_, select
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.auth import AuthSession, AuthToken, RateLimitBucket
from app.models.check import CheckRun
from app.models.monitor import Monitor

BATCH_SIZE = 500


def prune_history(engine: Engine) -> None:
    with Session(engine) as db, db.begin():
        now = db.scalar(select(func.clock_timestamp()))
        assert now is not None
        old = (
            CheckRun.state.in_(("completed", "cancelled", "infrastructure_failed")),
            CheckRun.completed_at < now - timedelta(days=30),
        )
        # Incident FK updates can touch several runs for one monitor. Match the worker's
        # monitor-before-run order, and serialize concurrent pruning for that monitor.
        monitors = list(
            db.scalars(
                select(Monitor.id)
                .where(select(CheckRun.id).where(CheckRun.monitor_id == Monitor.id, *old).exists())
                .order_by(Monitor.id)
                .limit(BATCH_SIZE)
                .with_for_update(skip_locked=True)
            )
        )
        ids = (
            select(CheckRun.id)
            .where(CheckRun.monitor_id.in_(monitors), *old)
            .order_by(CheckRun.completed_at, CheckRun.id)
            .limit(BATCH_SIZE)
            .with_for_update(skip_locked=True)
        )
        db.execute(delete(CheckRun).where(CheckRun.id.in_(ids)))
    # Each batch gets its own short transaction; busy rows are skipped until the next sweep.
    with Session(engine) as db, db.begin():
        sessions = (
            select(AuthSession.id)
            .where(
                or_(
                    AuthSession.expires_at < now,
                    AuthSession.last_activity_at < now - timedelta(hours=24),
                )
            )
            .order_by(AuthSession.expires_at)
            .limit(BATCH_SIZE)
            .with_for_update(skip_locked=True)
        )
        db.execute(delete(AuthSession).where(AuthSession.id.in_(sessions)))
    with Session(engine) as db, db.begin():
        tokens = (
            select(AuthToken.id)
            .where(
                or_(
                    AuthToken.expires_at < now - timedelta(days=1),
                    AuthToken.consumed_at < now - timedelta(days=1),
                )
            )
            .order_by(AuthToken.expires_at)
            .limit(BATCH_SIZE)
            .with_for_update(skip_locked=True)
        )
        db.execute(delete(AuthToken).where(AuthToken.id.in_(tokens)))
    with Session(engine) as db, db.begin():
        buckets = (
            select(RateLimitBucket.scope_hash)
            .where(RateLimitBucket.expires_at < now)
            .order_by(RateLimitBucket.expires_at)
            .limit(BATCH_SIZE)
            .with_for_update(skip_locked=True)
        )
        db.execute(delete(RateLimitBucket).where(RateLimitBucket.scope_hash.in_(buckets)))
    logger.info("retention_completed", extra={"event": "retention_completed"})
