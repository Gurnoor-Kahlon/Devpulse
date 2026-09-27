import base64
import binascii
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, text, tuple_
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.security import now_utc
from app.models.assertion import Assertion
from app.models.auth import User
from app.models.monitor import Monitor
from app.schemas.monitors import MonitorCreate, MonitorPage, MonitorResponse, MonitorUpdate

ACCOUNT_LIMIT = 10
ENABLED_LIMIT = 100
# Application-reserved PostgreSQL transaction lock, shared by all monitor writers.
QUOTA_LOCK = 7157001


def lock_monitor_writes(db: Session, user_id: UUID) -> User:
    # Serialize quota counts + mutations across API processes; release on commit/rollback.
    # Keep lock order global quota -> user -> monitor. No network work in this transaction.
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": QUOTA_LOCK})
    user = db.scalar(
        select(User)
        .where(User.id == user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if user is None:
        raise ApiError(401, "authentication_required", "Sign in to continue.")
    return user


def require_verified(user: User) -> None:
    if user.email_verified_at is None:
        raise ApiError(
            403, "email_verification_required", "Verify your email to create or enable monitors."
        )


def check_enabled_quota(db: Session) -> None:
    count = db.scalar(
        select(func.count())
        .select_from(Monitor)
        .where(
            Monitor.deleted_at.is_(None),
            Monitor.enabled.is_(True),
        )
    )
    if count is not None and count >= ENABLED_LIMIT:
        raise ApiError(
            409,
            "enabled_monitor_quota_exceeded",
            "The service has reached its limit of 100 enabled monitors. Try again later.",
        )


def owned_monitor(db: Session, user_id: UUID, monitor_id: UUID, *, lock: bool = False) -> Monitor:
    query = select(Monitor).where(
        Monitor.id == monitor_id,
        Monitor.user_id == user_id,
        Monitor.deleted_at.is_(None),
    )
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    monitor = db.scalar(query)
    if monitor is None:
        raise ApiError(404, "monitor_not_found", "Monitor not found.")
    return monitor


def check_version(monitor: Monitor, version: int) -> None:
    if monitor.configuration_version != version:
        raise ApiError(
            409, "configuration_conflict", "This monitor changed. Reload it before trying again."
        )


def create_monitor(db: Session, user_id: UUID, body: MonitorCreate) -> Monitor:
    user = lock_monitor_writes(db, user_id)
    require_verified(user)
    count = db.scalar(
        select(func.count())
        .select_from(Monitor)
        .where(
            Monitor.user_id == user_id,
            Monitor.deleted_at.is_(None),
        )
    )
    if count is not None and count >= ACCOUNT_LIMIT:
        raise ApiError(
            409,
            "monitor_quota_exceeded",
            "Your account has reached its limit of 10 monitors. Archive a monitor to add another.",
        )
    if body.enabled:
        check_enabled_quota(db)
    monitor = Monitor(
        user_id=user_id, **body.model_dump(), next_due_at=now_utc() if body.enabled else None
    )
    db.add(monitor)
    db.commit()
    return monitor


def update_monitor(db: Session, user_id: UUID, monitor_id: UUID, body: MonitorUpdate) -> Monitor:
    user = lock_monitor_writes(db, user_id)
    monitor = owned_monitor(db, user_id, monitor_id, lock=True)
    check_version(monitor, body.configuration_version)
    changes = body.model_dump(exclude_unset=True, exclude={"configuration_version"})
    if changes.get("method") == "HEAD" and db.scalar(
        select(Assertion.id).where(Assertion.monitor_id == monitor.id).limit(1)
    ):
        raise ApiError(
            422, "assertions_require_get", "Remove body assertions before choosing HEAD."
        )
    if changes.get("enabled") is True:
        require_verified(user)
        if not monitor.enabled:
            check_enabled_quota(db)
    changes = {key: value for key, value in changes.items() if getattr(monitor, key) != value}
    if changes:
        for key, value in changes.items():
            setattr(monitor, key, value)
        monitor.configuration_version += 1
        monitor.last_scheduled_check_at = None
        monitor.updated_at = now_utc()
        # Settings become eligible immediately; renaming does not shift the schedule.
        if changes.keys() - {"name"}:
            monitor.next_due_at = monitor.updated_at if monitor.enabled else None
    db.commit()
    return monitor


def archive_monitor(db: Session, user_id: UUID, monitor_id: UUID, version: int) -> None:
    lock_monitor_writes(db, user_id)
    monitor = owned_monitor(db, user_id, monitor_id, lock=True)
    check_version(monitor, version)
    monitor.deleted_at = monitor.updated_at = now_utc()
    monitor.enabled = False
    monitor.next_due_at = None
    monitor.configuration_version += 1
    # Preserve health and check timestamps; archiving is not observed recovery.
    db.commit()


def encode_cursor(monitor: Monitor) -> str:
    value = f"{monitor.created_at.isoformat()}|{monitor.id}".encode("ascii")
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        raw = base64.b64decode(cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True)
        timestamp, identifier = raw.decode("ascii").split("|")
        created_at = datetime.fromisoformat(timestamp)
        if created_at.utcoffset() is None:
            raise ValueError("Timezone required")
        return created_at, UUID(identifier)
    except (ValueError, UnicodeError, binascii.Error):
        raise ApiError(
            422, "invalid_cursor", "Use a cursor returned by the monitor list."
        ) from None


def list_monitors(db: Session, user_id: UUID, limit: int, cursor: str | None) -> MonitorPage:
    query = select(Monitor).where(Monitor.user_id == user_id, Monitor.deleted_at.is_(None))
    if cursor is not None:
        created_at, identifier = decode_cursor(cursor)
        query = query.where(tuple_(Monitor.created_at, Monitor.id) < (created_at, identifier))
    rows = list(
        db.scalars(query.order_by(Monitor.created_at.desc(), Monitor.id.desc()).limit(limit + 1))
    )
    page = rows[:limit]
    return MonitorPage(
        items=[MonitorResponse.model_validate(row) for row in page],
        next_cursor=encode_cursor(page[-1]) if len(rows) > limit else None,
    )
