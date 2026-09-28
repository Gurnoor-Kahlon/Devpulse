import time
from datetime import timedelta
from uuid import UUID, uuid4

from kombu.exceptions import OperationalError  # type: ignore[import-untyped]
from redis.exceptions import RedisError
from sqlalchemy import Engine, and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.logging import logger
from app.jobs.configuration import NOTIFICATION_TASK, create_celery
from app.models.notification import NotificationDelivery

BATCH_SIZE = 25
REPUBLISH_SECONDS = 30


def reserve_deliveries(engine: Engine) -> list[UUID]:
    with Session(engine) as db, db.begin():
        now = db.scalar(select(func.clock_timestamp()))
        assert now is not None
        rows = list(
            db.scalars(
                select(NotificationDelivery)
                .where(
                    NotificationDelivery.next_publish_at <= now,
                    or_(
                        and_(
                            NotificationDelivery.status == "pending",
                            NotificationDelivery.next_attempt_at <= now,
                        ),
                        and_(
                            NotificationDelivery.status == "sending",
                            NotificationDelivery.lease_expires_at <= now,
                        ),
                    ),
                )
                .order_by(NotificationDelivery.next_publish_at, NotificationDelivery.id)
                .limit(BATCH_SIZE)
                .with_for_update(skip_locked=True)
            )
        )
        for row in rows:
            row.next_publish_at = now + timedelta(seconds=REPUBLISH_SECONDS)
        return [row.id for row in rows]


def publish_delivery(settings: Settings, identifier: UUID) -> bool:
    app = create_celery(settings)
    try:
        with app.connection_for_write() as connection:
            connection.ensure_connection(max_retries=0)
            with app.amqp.Producer(connection) as producer:
                app.send_task(
                    NOTIFICATION_TASK,
                    args=[str(identifier)],
                    task_id=str(uuid4()),
                    producer=producer,
                    retry=False,
                )
    except (OperationalError, RedisError, OSError):
        logger.warning(
            "notification_deferred",
            extra={
                "event": "notification_deferred",
                "delivery_id": str(identifier),
                "error_code": "broker_unavailable",
            },
        )
        return False
    finally:
        app.close()
    return True


def dispatch_deliveries(engine: Engine, settings: Settings) -> None:
    identifiers = reserve_deliveries(engine)
    deadline = time.monotonic() + 15
    for identifier in identifiers:
        if time.monotonic() >= deadline or not publish_delivery(settings, identifier):
            break  # Every unacknowledged reservation becomes due again after its cooldown.
