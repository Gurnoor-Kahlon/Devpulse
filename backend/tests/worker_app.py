"""Real Celery tasks with only their database namespace isolated for process tests."""

import os
import re

from sqlalchemy import Engine, create_engine

from app.core.config import Settings
from app.jobs import tasks
from app.jobs.celery_app import celery_app  # noqa: F401


def isolated_engine(settings: Settings) -> Engine:
    schema = os.environ["TEST_WORKER_SCHEMA"]
    if settings.environment != "test" or not re.fullmatch(r"test_[a-f0-9]{32}", schema):
        raise RuntimeError("A generated test schema is required.")
    return create_engine(
        settings.database_url.get_secret_value(),
        hide_parameters=True,
        connect_args={
            "connect_timeout": 3,
            "options": (
                f"-c search_path={schema} -c timezone=UTC "
                "-c statement_timeout=5000 -c lock_timeout=3000"
            ),
        },
    )


tasks.create_database_engine = isolated_engine
