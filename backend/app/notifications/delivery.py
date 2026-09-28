"""Fenced SMTP attempts, with PostgreSQL-owned retries and no transaction during SMTP."""

import os
import smtplib
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.logging import logger
from app.models.auth import User
from app.models.incident import Incident
from app.models.notification import NotificationChannel, NotificationDelivery
from app.notifications.email import incident_message
from app.services.mail import send_message

LEASE_SECONDS = 60
MAX_ATTEMPTS = 5
BACKOFF_SECONDS = (30, 120, 600, 1800)


@dataclass(frozen=True)
class DeliverySpec:
    id: UUID
    lease_token: UUID
    destination: str
    incident_id: UUID
    transition: str
    monitor_name: str
    started_at: datetime
    confirmed_at: datetime
    resolved_at: datetime | None


def enabled(channel: NotificationChannel, transition: str) -> bool:
    return channel.enabled and (channel.on_open if transition == "opened" else channel.on_recovery)


def terminal(row: NotificationDelivery, status: str, now: datetime, code: str | None) -> None:
    row.status, row.completed_at, row.last_error_code = status, now, code
    row.next_attempt_at = row.lease_expires_at = None
    row.lease_token = None


def claim_delivery(engine: Engine, identifier: UUID) -> DeliverySpec | None:
    with Session(engine) as db, db.begin():
        cid = db.scalar(
            select(NotificationDelivery.channel_id).where(NotificationDelivery.id == identifier)
        )
        if cid is None:
            return None
        channel = db.scalar(
            select(NotificationChannel).where(NotificationChannel.id == cid).with_for_update()
        )
        row = db.scalar(
            select(NotificationDelivery)
            .where(NotificationDelivery.id == identifier)
            .with_for_update()
        )
        assert row is not None and channel is not None
        now = db.scalar(select(func.clock_timestamp()))
        assert now is not None
        if row.status not in {"pending", "sending"}:
            return None
        if row.status == "sending" and row.lease_expires_at and row.lease_expires_at > now:
            return None
        if row.status == "pending" and row.next_attempt_at and row.next_attempt_at > now:
            return None
        user = db.get(User, channel.user_id)
        if (
            user is None
            or user.email_verified_at is None
            or row.cancel_requested
            or not enabled(channel, row.transition)
        ):
            terminal(
                row,
                "cancelled",
                now,
                "email_unverified"
                if user is None or user.email_verified_at is None
                else "preferences_disabled",
            )
            return None
        if row.attempt_count >= MAX_ATTEMPTS:
            terminal(row, "failed", now, "delivery_unknown")
            return None
        if row.transition == "resolved" and db.scalar(
            select(NotificationDelivery.id).where(
                NotificationDelivery.incident_id == row.incident_id,
                NotificationDelivery.channel_id == cid,
                NotificationDelivery.transition == "opened",
                NotificationDelivery.status.in_(("pending", "sending")),
            )
        ):
            return None  # Keep recorded transition order even when confirmation needs retries.
        incident = db.get(Incident, row.incident_id)
        assert incident is not None
        row.status, row.next_attempt_at = "sending", None
        row.lease_token = uuid4()
        row.lease_expires_at = now + timedelta(seconds=LEASE_SECONDS)
        row.attempt_count += 1  # Crashed attempts consume the bounded retry budget too.
        return DeliverySpec(
            row.id,
            row.lease_token,
            user.email,
            incident.id,
            row.transition,
            incident.monitor_name,
            incident.started_at,
            incident.confirmed_at,
            incident.resolved_at,
        )


def finish_delivery(
    engine: Engine, spec: DeliverySpec, code: str | None, permanent: bool = False
) -> bool:
    with Session(engine) as db, db.begin():
        cid = db.scalar(
            select(NotificationDelivery.channel_id).where(NotificationDelivery.id == spec.id)
        )
        if cid is None:
            return False
        channel = db.scalar(
            select(NotificationChannel).where(NotificationChannel.id == cid).with_for_update()
        )
        row = db.scalar(
            select(NotificationDelivery).where(NotificationDelivery.id == spec.id).with_for_update()
        )
        assert channel is not None and row is not None
        now = db.scalar(select(func.clock_timestamp()))
        assert now is not None
        if (
            row.status != "sending"
            or row.lease_token != spec.lease_token
            or row.lease_expires_at is None
            or row.lease_expires_at <= now
        ):
            return False
        if code is None:
            terminal(row, "sent", now, None)
        elif row.cancel_requested or not enabled(channel, row.transition):
            terminal(row, "cancelled", now, "preferences_disabled")
        elif permanent or row.attempt_count >= MAX_ATTEMPTS:
            terminal(row, "failed", now, code)
        else:
            row.status, row.last_error_code = "pending", code
            row.lease_token = row.lease_expires_at = None
            row.next_attempt_at = now + timedelta(seconds=BACKOFF_SECONDS[row.attempt_count - 1])
            row.next_publish_at = row.next_attempt_at
        return True


def deliver(engine: Engine, settings: Settings, identifier: UUID) -> None:
    spec = claim_delivery(engine, identifier)
    if spec is None:
        return
    logger.info(
        "notification_started",
        extra={
            "event": "notification_started",
            "delivery_id": str(spec.id),
            "worker_pid": os.getpid(),
        },
    )
    code = None
    permanent = False
    try:
        send_message(settings, incident_message(settings, spec))
    except smtplib.SMTPRecipientsRefused as exc:
        code = "smtp_rejected"
        permanent = bool(exc.recipients) and all(
            500 <= value[0] < 600 for value in exc.recipients.values()
        )
    except smtplib.SMTPResponseException as exc:
        code = "smtp_rejected"
        permanent = 500 <= exc.smtp_code < 600
    except (OSError, smtplib.SMTPException):
        code = "smtp_unavailable"
    stored = finish_delivery(engine, spec, code, permanent)
    logger.info(
        "notification_attempt",
        extra={
            "event": "notification_attempt",
            "delivery_id": str(spec.id),
            "error_code": code,
            "outcome": "stored" if stored else "obsolete",
        },
    )
