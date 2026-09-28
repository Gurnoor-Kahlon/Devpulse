import base64
from uuid import UUID

from sqlalchemy import select, tuple_, update
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.security import now_utc
from app.models.auth import User
from app.models.incident import Incident
from app.models.monitor import Monitor
from app.models.notification import NotificationChannel, NotificationDelivery
from app.schemas.notifications import (
    DeliveryPage,
    DeliveryResponse,
    NotificationPreferences,
    NotificationUpdate,
)
from app.services.incidents import cursor_value


def preferences(db: Session, user_id: UUID) -> NotificationPreferences:
    user = db.get(User, user_id)
    assert user is not None
    channel = db.scalar(select(NotificationChannel).where(NotificationChannel.user_id == user_id))
    return NotificationPreferences(
        configuration_version=channel.configuration_version if channel else 0,
        enabled=channel.enabled if channel else False,
        on_open=channel.on_open if channel else True,
        on_recovery=channel.on_recovery if channel else True,
        destination=user.email,
        verified=user.email_verified_at is not None,
    )


def update_preferences(
    db: Session, user_id: UUID, body: NotificationUpdate
) -> NotificationPreferences:
    # Serialize creation of the single channel as well as its subsequent edits.
    user = db.scalar(select(User).where(User.id == user_id).with_for_update())
    assert user is not None
    channel = db.scalar(
        select(NotificationChannel).where(NotificationChannel.user_id == user_id).with_for_update()
    )
    if body.configuration_version != (channel.configuration_version if channel else 0):
        raise ApiError(
            409, "configuration_conflict", "Reload notification preferences and try again."
        )
    if body.enabled and user.email_verified_at is None:
        raise ApiError(
            403, "email_verification_required", "Verify your email before enabling notifications."
        )
    values = body.model_dump(exclude={"configuration_version"})
    if channel is None:
        channel = NotificationChannel(user_id=user_id, **values)
        db.add(channel)
        db.flush()
    elif any(getattr(channel, k) != v for k, v in values.items()):
        for key, value in values.items():
            setattr(channel, key, value)
        channel.configuration_version += 1
    # Cancel only unclaimed work. An already claimed SMTP send cannot be recalled.
    disabled = []
    if not body.enabled or not body.on_open:
        disabled.append("opened")
    if not body.enabled or not body.on_recovery:
        disabled.append("resolved")
    db.execute(
        update(NotificationDelivery)
        .where(
            NotificationDelivery.channel_id == channel.id,
            NotificationDelivery.status == "pending",
            NotificationDelivery.transition.in_(disabled),
        )
        .values(
            status="cancelled",
            next_attempt_at=None,
            completed_at=now_utc(),
            last_error_code="preferences_disabled",
        )
    )
    db.execute(
        update(NotificationDelivery)
        .where(
            NotificationDelivery.channel_id == channel.id,
            NotificationDelivery.status == "sending",
            NotificationDelivery.transition.in_(disabled),
        )
        .values(cancel_requested=True)
    )
    db.flush()
    result = preferences(db, user_id)
    db.commit()
    return result


def list_deliveries(
    db: Session, user_id: UUID, limit: int, cursor: str | None, incident_id: UUID | None
) -> DeliveryPage:
    if (
        incident_id is not None
        and db.scalar(
            select(Incident.id)
            .join(Monitor)
            .where(Incident.id == incident_id, Monitor.user_id == user_id)
        )
        is None
    ):
        raise ApiError(404, "incident_not_found", "Incident not found.")
    query = (
        select(NotificationDelivery)
        .join(NotificationChannel)
        .where(NotificationChannel.user_id == user_id)
    )
    if incident_id is not None:
        query = query.where(NotificationDelivery.incident_id == incident_id)
    if cursor:
        query = query.where(
            tuple_(NotificationDelivery.created_at, NotificationDelivery.id) < cursor_value(cursor)
        )
    rows = list(
        db.scalars(
            query.order_by(
                NotificationDelivery.created_at.desc(), NotificationDelivery.id.desc()
            ).limit(limit + 1)
        )
    )
    page = rows[:limit]
    next_cursor = None
    if len(rows) > limit:
        next_cursor = (
            base64.urlsafe_b64encode(
                f"{page[-1].created_at.isoformat()}|{page[-1].id}".encode("ascii")
            )
            .decode("ascii")
            .rstrip("=")
        )
    return DeliveryPage(
        items=[DeliveryResponse.model_validate(r) for r in page], next_cursor=next_cursor
    )
