import os
from uuid import UUID

from celery import current_task  # type: ignore[import-untyped]
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import load_settings
from app.core.logging import logger
from app.db.session import create_database_engine
from app.jobs.celery_app import celery_app
from app.jobs.configuration import DISPATCH_TASK, PROBE_TASK
from app.jobs.dispatcher import dispatch_runs
from app.monitoring.runs import claim_run, execute_spec, finish_run


def execute_job(run_id: str) -> None:
    try:
        identifier = UUID(run_id)
    except (ValueError, TypeError, AttributeError):
        logger.warning("job_rejected", extra={"event": "job_rejected"})
        return
    job_id = getattr(current_task.request, "id", None) if current_task else None
    # Only UUID identifiers belong in logs, even if a malformed broker message is received.
    try:
        job_id = str(UUID(str(job_id)))
    except ValueError:
        job_id = None
    fields = {"run_id": str(identifier), "job_id": job_id, "worker_pid": os.getpid()}
    settings = load_settings()
    # Created after fork for each task; no inherited engine, session, or HTTP client.
    engine = create_database_engine(settings)
    try:
        spec = claim_run(engine, identifier)
        if spec is None:
            logger.info("job_ignored", extra={"event": "job_ignored", **fields})
            return
        logger.info("job_started", extra={"event": "job_started", **fields})
        result = execute_spec(spec, settings)
        check_id = finish_run(engine, spec, result)
        logger.info(
            "job_finished",
            extra={
                "event": "job_finished",
                **fields,
                "outcome": "stored" if check_id else "obsolete",
            },
        )
    except SQLAlchemyError:
        # No target-failure result is manufactured. Pending work/expired leases can be republished.
        logger.error(
            "job_deferred",
            extra={"event": "job_deferred", **fields, "error_code": "persistence_unavailable"},
        )
    finally:
        engine.dispose()


celery_app.task(name=PROBE_TASK, ignore_result=True)(execute_job)


def dispatch_job() -> None:
    settings = load_settings()
    engine = create_database_engine(settings)
    try:
        dispatch_runs(engine, settings)
    except SQLAlchemyError:
        logger.error(
            "scheduler_deferred",
            extra={"event": "scheduler_deferred", "error_code": "persistence_unavailable"},
        )
    finally:
        engine.dispose()


celery_app.task(name=DISPATCH_TASK, ignore_result=True)(dispatch_job)
