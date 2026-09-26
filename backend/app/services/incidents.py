import base64
import binascii
from datetime import datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models.incident import Incident
from app.models.monitor import Monitor
from app.schemas.incidents import IncidentDetail, IncidentPage, IncidentResponse


def cursor_value(value: str) -> tuple[datetime, UUID]:
    try:
        raw = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
        timestamp, identifier = raw.decode("ascii").split("|")
        started = datetime.fromisoformat(timestamp)
        if started.utcoffset() is None:
            raise ValueError
        return started, UUID(identifier)
    except (ValueError, UnicodeError, binascii.Error):
        raise ApiError(
            422, "invalid_cursor", "Use a cursor returned by the incident list."
        ) from None


def list_incidents(
    db: Session,
    user_id: UUID,
    limit: int,
    cursor: str | None,
    status: Literal["open", "resolved"] | None,
    monitor_id: UUID | None,
) -> IncidentPage:
    # Archived monitors remain owned and keep their incident history.
    if (
        monitor_id is not None
        and db.scalar(
            select(Monitor.id).where(Monitor.id == monitor_id, Monitor.user_id == user_id)
        )
        is None
    ):
        raise ApiError(404, "monitor_not_found", "Monitor not found.")
    query = (
        select(Incident)
        .join(Monitor, Monitor.id == Incident.monitor_id)
        .where(Monitor.user_id == user_id)
    )
    if monitor_id is not None:
        query = query.where(Incident.monitor_id == monitor_id)
    if status is not None:
        query = query.where(
            Incident.resolved_at.is_(None)
            if status == "open"
            else Incident.resolved_at.is_not(None)
        )
    if cursor is not None:
        query = query.where(tuple_(Incident.started_at, Incident.id) < cursor_value(cursor))
    rows = list(
        db.scalars(query.order_by(Incident.started_at.desc(), Incident.id.desc()).limit(limit + 1))
    )
    page = rows[:limit]
    next_cursor = None
    if len(rows) > limit:
        value = f"{page[-1].started_at.isoformat()}|{page[-1].id}".encode("ascii")
        next_cursor = base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")
    return IncidentPage(
        items=[IncidentResponse.model_validate(row) for row in page], next_cursor=next_cursor
    )


def get_incident(db: Session, user_id: UUID, incident_id: UUID) -> IncidentDetail:
    row = db.scalar(
        select(Incident)
        .join(Monitor, Monitor.id == Incident.monitor_id)
        .where(Incident.id == incident_id, Monitor.user_id == user_id)
    )
    if row is None:
        raise ApiError(404, "incident_not_found", "Incident not found.")
    return IncidentDetail.model_validate(row)
