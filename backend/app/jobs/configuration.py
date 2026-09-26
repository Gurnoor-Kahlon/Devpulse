import ssl

from celery import Celery  # type: ignore[import-untyped]
from kombu import Queue  # type: ignore[import-untyped]

from app.core.config import Settings

PROBE_TASK = "devpulse.probe.execute"
PROBE_QUEUE = "probes"
DISPATCH_TASK = "devpulse.scheduler.dispatch"
MAINTENANCE_QUEUE = "maintenance"


def create_celery(settings: Settings) -> Celery:
    app = Celery(
        "devpulse", broker=settings.broker_url.get_secret_value(), include=["app.jobs.tasks"]
    )
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_backend=None,
        task_ignore_result=True,
        task_store_errors_even_if_ignored=False,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        task_acks_on_failure_or_timeout=True,
        task_default_queue=PROBE_QUEUE,
        task_queues=(Queue(PROBE_QUEUE), Queue(MAINTENANCE_QUEUE)),
        task_routes={
            PROBE_TASK: {"queue": PROBE_QUEUE},
            DISPATCH_TASK: {"queue": MAINTENANCE_QUEUE},
        },
        beat_schedule={
            "dispatch-monitors": {"task": DISPATCH_TASK, "schedule": 5.0, "options": {"expires": 5}}
        },
        beat_max_loop_interval=5,
        task_create_missing_queues=False,
        task_publish_retry=False,
        broker_connection_timeout=3,
        broker_connection_retry_on_startup=True,
        broker_transport_options={
            "visibility_timeout": 90,
            "global_keyprefix": settings.broker_key_prefix,
            "socket_connect_timeout": 3,
            "socket_timeout": 3,
            "retry_on_timeout": False,
        },
        broker_use_ssl={"ssl_cert_reqs": ssl.CERT_REQUIRED}
        if settings.broker_url.get_secret_value().startswith("rediss://")
        else None,
        worker_concurrency=2,
        worker_prefetch_multiplier=1,
        worker_cancel_long_running_tasks_on_connection_loss=True,
        worker_enable_remote_control=False,
        worker_send_task_events=False,
        task_send_sent_event=False,
        worker_hijack_root_logger=False,
        task_soft_time_limit=40,
        task_time_limit=45,
        timezone="UTC",
        enable_utc=True,
    )
    return app
