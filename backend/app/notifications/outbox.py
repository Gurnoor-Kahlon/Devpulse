"""Record delivery intent inside the incident transaction; never perform external I/O."""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.incident import Incident
from app.models.monitor import Monitor
from app.models.notification import NotificationChannel, NotificationDelivery


def enqueue_transition(db: Session, monitor: Monitor, incident: Incident, transition: str) -> None:
    channel = db.scalar(
        select(NotificationChannel)
        .where(NotificationChannel.user_id == monitor.user_id)
        .with_for_update()
    )
    user = db.get(User, monitor.user_id)
    if channel is None or not channel.enabled or user is None or user.email_verified_at is None:
        return
    if not (channel.on_open if transition == "opened" else channel.on_recovery):
        return
    db.flush()
    db.execute(
        insert(NotificationDelivery)
        .values(incident_id=incident.id, channel_id=channel.id, transition=transition)
        .on_conflict_do_nothing(index_elements=["incident_id", "transition", "channel_id"])
    )
