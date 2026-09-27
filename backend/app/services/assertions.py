from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.security import now_utc
from app.models.assertion import Assertion
from app.models.monitor import Monitor
from app.schemas.assertions import (
    AssertionDefinition,
    AssertionPage,
    AssertionSnapshot,
    AssertionUpdate,
)
from app.services.monitors import check_version, lock_monitor_writes, owned_monitor


def snapshots(db: Session, monitor_id: UUID) -> tuple[AssertionSnapshot, ...]:
    return tuple(
        AssertionSnapshot.model_validate(
            dict(id=row.id, kind=row.kind, pointer=row.pointer, expected=row.expected)
        )
        for row in db.scalars(
            select(Assertion).where(Assertion.monitor_id == monitor_id).order_by(Assertion.position)
        )
    )


def page(db: Session, monitor: Monitor) -> AssertionPage:
    return AssertionPage.model_validate(
        dict(
            monitor_id=monitor.id,
            configuration_version=monitor.configuration_version,
            method=monitor.method,
            items=list(snapshots(db, monitor.id)),
        )
    )


def get_assertions(db: Session, user_id: UUID, monitor_id: UUID) -> AssertionPage:
    return page(db, owned_monitor(db, user_id, monitor_id))


def replace_assertions(
    db: Session, user_id: UUID, monitor_id: UUID, body: AssertionUpdate
) -> AssertionPage:
    lock_monitor_writes(db, user_id)
    monitor = owned_monitor(db, user_id, monitor_id, lock=True)
    check_version(monitor, body.configuration_version)
    if monitor.method == "HEAD" and body.items:
        raise ApiError(422, "assertions_require_get", "Body assertions require a GET monitor.")
    existing = [
        AssertionDefinition(**item.model_dump(exclude={"id"})) for item in snapshots(db, monitor.id)
    ]
    if [item.model_dump_json() for item in existing] != [
        item.model_dump_json() for item in body.items
    ]:
        db.execute(delete(Assertion).where(Assertion.monitor_id == monitor.id))
        for position, item in enumerate(body.items):
            db.add(Assertion(monitor_id=monitor.id, position=position, **item.model_dump()))
        monitor.configuration_version += 1
        monitor.last_scheduled_check_at = None
        monitor.updated_at = now_utc()
        monitor.next_due_at = monitor.updated_at if monitor.enabled else None
        db.flush()
    result = page(db, monitor)
    db.commit()
    return result
