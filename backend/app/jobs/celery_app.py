from celery import signals  # type: ignore[import-untyped]

from app.core.config import load_settings
from app.core.logging import configure_logging, logger
from app.jobs.configuration import create_celery

celery_app = create_celery(load_settings())


def setup_worker_logging(**kwargs: object) -> None:
    configure_logging(load_settings().log_level)


signals.setup_logging.connect(setup_worker_logging)


def report_worker_ready(**kwargs: object) -> None:
    logger.info("worker_ready", extra={"event": "worker_ready"})


signals.worker_ready.connect(report_worker_ready)
