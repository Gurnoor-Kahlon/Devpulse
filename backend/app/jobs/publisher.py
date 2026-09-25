from uuid import UUID, uuid4

from kombu.exceptions import OperationalError  # type: ignore[import-untyped]
from redis.exceptions import RedisError
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.logging import logger
from app.jobs.configuration import PROBE_TASK, create_celery
from app.models.check import CheckRun
from app.monitoring.runs import RunError


def publish_run(engine: Engine, settings: Settings, run_id: UUID) -> bool:
    with Session(engine) as db:
        state = db.scalar(select(CheckRun.state).where(CheckRun.id == run_id))
        if state not in {"pending", "running"}:
            raise RunError("Run is absent or already finished.")
    job_id = str(uuid4())
    # Publication cannot be atomic with PostgreSQL. Keep the durable row regardless of outcome.
    app = create_celery(settings)
    try:
        with app.connection_for_write() as connection:
            connection.ensure_connection(max_retries=0)
            with app.amqp.Producer(connection) as producer:
                app.send_task(
                    PROBE_TASK, args=[str(run_id)], task_id=job_id, producer=producer, retry=False
                )
    except (OperationalError, RedisError, OSError):
        logger.warning(
            "job_publish_failed",
            extra={"event": "job_publish_failed", "run_id": str(run_id), "job_id": job_id},
        )
        return False
    finally:
        app.close()
    logger.info(
        "job_published", extra={"event": "job_published", "run_id": str(run_id), "job_id": job_id}
    )
    return True
